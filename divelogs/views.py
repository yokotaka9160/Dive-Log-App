from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, ExpressionWrapper, DurationField, F, Max, Q
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    TemplateView,
)

from .forms import DiveLogForm, DiveLogFilterForm
from .models import DiveLog
from datetime import timedelta
from django.views.decorators.http import require_POST
from google import genai
from google.genai import errors, types
from django.http import JsonResponse
from django.conf import settings

# 並び替えの選択肢: キー -> (ラベル, order_by 引数)
SORT_FIELDS = {
    "date":"dive_date",
    "max_depth":"max_depth",
    "duration":"duration_db",
    "transparency":"transparency",
    "pressure":"pressure_used_db",
    "bottom_temp":"w_bottom_temp",
}


def landing(request):
    """ログイン/サインアップのみを選べるトップページ。"""
    if request.user.is_authenticated:
        return redirect("divelogs:log_list")
    return render(request, "logs/landing.html")


class LogListView(ListView):
    model = DiveLog
    template_name = "logs/log_list.html"
    context_object_name = "logs"
    paginate_by = 9

    def get_queryset(self):
        qs = DiveLog.objects.select_related("user").annotate(
            duration_db=ExpressionWrapper(
                F("exit_date") - F("entry_date"), output_field=DurationField()
            ),
            pressure_used_db=F("start_press") - F("end_press"),
        )    

        # 自分の投稿のみ
        if self.request.GET.get("mine") == "1" and self.request.user.is_authenticated:
            qs = qs.filter(user=self.request.user)

        # 絞り込み（画面から送られた値をフォームで検証してから使う）
        self.filter_form = DiveLogFilterForm(self.request.GET)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data["q"]:
                qs = qs.filter(
                                Q(location__icontains=data["q"])
                                | Q(dive_point_name__icontains=data["q"])
                                | Q(fish__icontains=data["q"])
                                | Q(buddy_name__icontains=data["q"])
                                | Q(inst_name__icontains=data["q"])
                                | Q(free_text_field__icontains=data["q"])
                            )
            if data["date_from"]:
                qs = qs.filter(dive_date__gte=data["date_from"])
            if data["date_to"]:
                qs = qs.filter(dive_date__lte=data["date_to"])
            if data["entry_way"]:
                qs = qs.filter(entry_way=data["entry_way"])
            if data["depth_min"] is not None:
                qs = qs.filter(max_depth__gte=data["depth_min"])
            if data["depth_max"] is not None:
                qs = qs.filter(max_depth__lte=data["depth_max"])
            if data["dive_purpose"]:
                qs = qs.filter(dive_purpose=data["dive_purpose"])
            if data["weather"]:
                qs = qs.filter(weather=data["weather"])
            if data["current_str"]:
                qs = qs.filter(current_str=data["current_str"])
            if data["tank_type"]:
                qs = qs.filter(tank_type=data["tank_type"])
            if data["suit_type"]:
                qs = qs.filter(suit_type=data["suit_type"])
            if data["bottom_temp_min"] is not None:
                qs = qs.filter(w_bottom_temp__gte=data["bottom_temp_min"])
            if data["bottom_temp_max"] is not None:
                qs = qs.filter(w_bottom_temp__lte=data["bottom_temp_max"])
            if data["transparency_min"] is not None:
                qs = qs.filter(transparency__gte=data["transparency_min"])
            if data["transparency_max"] is not None:
                qs = qs.filter(transparency__lte=data["transparency_max"])
            if data["duration_min"] is not None:
                qs = qs.filter(duration_db__gte=timedelta(minutes=data["duration_min"]))

        # 並び替え
        sort = self.request.GET.get("sort", "date")
        field = SORT_FIELDS.get(sort, SORT_FIELDS["date"]) # 想定外の値なら日付順
        if self.request.GET.get("order") != "asc":   # asc 以外は大きい順（新しい順）
            field = "-" + field
        return qs.order_by(field,"-id")  # 値が同じときは、新しく登録した順

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mine_only"] = self.request.GET.get("mine") == "1"
        ctx["filter_form"] = self.filter_form
        return ctx
        # ctx = super().get_context_data(**kwargs)
        # ctx["query"] = self.request.GET.get("q", "")
        # ctx["current_sort"] = self.request.GET.get("sort", "new")
        # ctx["sort_options"] = SORT_OPTIONS
        # ctx["fav_only"] = self.request.GET.get("fav") == "1"
        # ctx["mine_only"] = self.request.GET.get("mine") == "1"
        # if self.request.user.is_authenticated:
        #     ctx["my_fav_ids"] = set(
        #         self.request.user.favorite_logs.values_list("id", flat=True)
        #     )
        # else:
        #     ctx["my_fav_ids"] = set()
        # # クエリ文字列を保持するためのベース（sort を除く）
        # return ctx

class LogDetailView(DetailView):
    model = DiveLog
    template_name = "logs/log_detail.html"
    context_object_name = "log"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 空のフォームインスタンスを渡すことで {{ form.〜.label }} が使えるようになる
        context["form"] = DiveLogForm()
        return context
    # def get_context_data(self, **kwargs):
    #     ctx = super().get_context_data(**kwargs)
    #     user = self.request.user
    #     ctx["is_favorited"] = (
    #         user.is_authenticated and self.object.favorites.filter(pk=user.pk).exists()
    #     )
    #     return ctx


class LogCreateView(LoginRequiredMixin, CreateView):
    model = DiveLog
    form_class = DiveLogForm
    template_name = "logs/log_form.html"
    # リダイレクト先を一覧画面（divelogs:log_list）などに指定
    success_url = reverse_lazy('divelogs:log_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "ダイブログを記録しました。")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "新しいダイブログ"
        ctx["submit_label"] = "記録する"
        return ctx


class OwnerRequiredMixin(UserPassesTestMixin):
    """投稿者本人のみ許可する。"""

    def test_func(self):
        return self.get_object().user == self.request.user


class LogUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = DiveLog
    form_class = DiveLogForm
    template_name = "logs/log_form.html"

    def form_valid(self, form):
        messages.success(self.request, "ダイブログを更新しました。")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "ダイブログを編集"
        ctx["submit_label"] = "更新する"
        return ctx
    
    def get_success_url(self):
        # 編集完了後、そのログの詳細ページへ遷移する
        return reverse('divelogs:log_detail', kwargs={'pk': self.object.pk})

class LogDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = DiveLog
    context_object_name = 'log'
    template_name = "logs/log_confirm_delete.html"
    success_url = reverse_lazy('divelogs:log_list')

    def form_valid(self, form):
        messages.success(self.request, "ダイブログを削除しました。")
        return super().form_valid(form)



# def signup(request):
#     if request.user.is_authenticated:
#         return redirect("log_list")
#     if request.method == "POST":
#         form = SignUpForm(request.POST)
#         if form.is_valid():
#             user = form.save()
#             login(request, user)
#             messages.success(request, "ようこそ、DEEPLOG へ。")
#             return redirect("log_list")
#     else:
#         form = SignUpForm()
#     return render(request, "registration/register.html", {"form": form})

class DashboardView(LoginRequiredMixin, TemplateView):  # ログイン必須の、テンプレートを表示するだけのビュー
    template_name = "logs/dashboard.html"  # 表示に使うテンプレート

    def get_context_data(self, **kwargs):  # テンプレートに渡す値（context）を用意するメソッド
        context = super().get_context_data(**kwargs)  # 親クラスが用意する標準の context を受け取る
        logs = DiveLog.objects.filter(user=self.request.user)  # ログイン中のユーザーのログだけに絞り込む（この時点ではまだ DB にアクセスしない）

        # 推移グラフは潜った順（エントリー日時の古い順）に並べる
        ordered = list(logs.order_by("entry_date", "id"))  # エントリー日時→ID の順に並べ、list() で DB から全件取得する
        context["total_logs"] = len(ordered)  # 通算本数 = 取得した件数
        if not ordered:  # ログが1件もない場合は
            return context  # 集計をせずに終了する（テンプレート側で「まだログがありません」を表示）

        # --- 数値サマリー ---
        durations = [log.duration_minutes for log in ordered if log.duration_minutes is not None]  # 1本ごとの潜水時間（分）を集める。計算できないログは除く
        context["total_minutes"] = sum(durations)  # 合計潜水時間 = 潜水時間の合計
        stats = logs.aggregate(max_depth=Max("max_depth"), max_ave_depth=Max("ave_depth"))  # DB 側で最大深度・平均深度それぞれの最大値を求める
        context["max_depth"] = stats["max_depth"]  # 過去最大深度
        context["max_ave_depth"] = stats["max_ave_depth"]  # 過去最大平均深度

        # --- 月別潜水本数 ---
        monthly = (
            logs.annotate(month=TruncMonth("dive_date"))  # 潜水日を「月の初日」に切り捨てた値を month として付ける
            .values("month")  # month ごとにグループ化する
            .annotate(count=Count("id"))  # グループごとの件数を count として数える
            .order_by("month")  # 月の古い順に並べる
        )
        context["monthly_chart"] = {  # 月別グラフ用のデータ
            "labels": [row["month"].strftime("%Y/%m") for row in monthly],  # 横軸のラベル（例: 2026/11）
            "values": [row["count"] for row in monthly],  # 棒の高さ（その月の本数）
        }

        # --- ダイブ目的の内訳（DB の値ではなく画面表示用のラベルにする） ---
        purpose_labels = dict(DiveLog.DivePurpose.choices)  # 選択肢を {DB の値: 表示名} の辞書にする
        purposes = logs.values("dive_purpose").annotate(count=Count("id")).order_by("-count")  # 目的ごとの件数を数え、多い順に並べる
        context["purpose_chart"] = {  # 円グラフ用のデータ
            "labels": [str(purpose_labels.get(row["dive_purpose"], row["dive_purpose"])) for row in purposes],  # 目的の表示名（辞書にない値はそのまま表示）
            "values": [row["count"] for row in purposes],  # 目的ごとの本数
        }

        # --- 推移グラフ（1本ごと） ---
        context["trend_chart"] = {  # 推移グラフ用のデータ（どのリストも ordered と同じ順番・同じ件数）
            "labels": [f"{i}本目" for i in range(1, len(ordered) + 1)],  # 横軸のラベル（1本目, 2本目, …）
            "dates": [log.dive_date.strftime("%Y/%m/%d") for log in ordered],  # ツールチップに出す潜水日
            "pressure_used": [log.start_press - log.end_press for log in ordered],  # 棒グラフ: タンク残圧（開始時−終了時）
            "max_depth": [log.max_depth for log in ordered],  # 折れ線: 最大深度
            "ave_depth": [log.ave_depth for log in ordered],  # 折れ線: 平均深度
            "duration": [log.duration_minutes for log in ordered],  # 折れ線: 潜水時間（分）
            "bottom_temp": [log.w_bottom_temp for log in ordered],  # 折れ線: 水底温度
        }
        return context  # 用意した context をテンプレートに渡す

PROMPT = """あなたは魚の種類を推定する専門家です。以下の条件に従って、アップロードされた画像に写っている魚の種類を推定してください。
条件:
1. 画像に写っている海の生物の名前をできるだけ正確に推定して、日本語の和名（カタカナ）で返してください。
2. 推定結果は名前のみを、１つづつリスト要素として返してください
3. 推定結果に余計な説明や文章は含めず、魚の名前のみを返してください。
4. 画像に海の生物が写っていない場合は、空のリスト を返してください。
5. 自信が無ければ何も返さないでください
"""

@login_required
@require_POST
def IdentifyFishView(request):
    """アップロードされた写真を解析し、魚の種類を推定するビュー。"""
    photo = request.FILES.get("photo")
    if not photo:
        return JsonResponse({"error": "画像がアップロードされていません。"}, status=400)
    if not photo.content_type.startswith("image/"):
        return JsonResponse({"error": "アップロードされたファイルは画像ではありません。"}, status=400)
    if photo.size > 10 * 1024 * 1024:  # 10MBの制限
        return JsonResponse({"error": "画像のサイズは10MB以下にしてください。"}, status=400)
    try:
        # Google Gemini API を使用して画像解析を行う
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=photo.read(), mime_type=photo.content_type),
            PROMPT,  
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[str],  # 返却される JSON の形式を指定
            ),
        )
        names = response.parsed or []  # 解析結果を取得。解析できなかった場合は空リスト
    except errors.APIError as e:
        print(e)
        if e.code == 429:
            return JsonResponse({"error": "画像解析のリクエストが多すぎます。しばらく待ってから再度お試しください。"}, status=429)
        return JsonResponse({"error": f"画像解析中にエラーが発生しました"}, status=502)

    # AI の返事を整える（空白を取る・空と重複を除く・最大5件）
    fish_list = []
    for name in names:
        name = name.strip()
        if not name or name in fish_list:
            continue
        fish_list.append(name)

    return JsonResponse({"fish": fish_list})