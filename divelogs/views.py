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

import re
from collections import Counter

from django.db import transaction

from .forms import DiveLogForm, DiveLogFilterForm
from .models import DiveLog, DiveLogPhoto
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
        # prefetch_related("photos")：カードの表紙・枚数のために、1 ページ分の写真を 1 回のクエリでまとめて読む
        qs = DiveLog.objects.select_related("user").prefetch_related("photos").annotate(
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


class PhotoSaveMixin:
    """フォームの写真（photos）を DiveLogPhoto として保存し、削除にチェックした写真を消す。

    DiveLogForm.save() が保存するのは DiveLog だけなので、写真はここで別に保存する。
    写真を結びつけるには DiveLog の pk が必要なので、必ず DiveLog を保存した後に呼ぶ。
    """

    def save_photos(self, form):
        log = self.object
        # 削除：フォームの clean() で「このログの写真」だけに絞り込んだ pk を使う
        for photo in log.photos.filter(pk__in=form.photo_ids_to_delete):
            photo.image.delete(save=False)  # 画像ファイルも消す
            photo.delete()
        # 追加：選ばれた順に 1 枚ずつ保存する
        for image in form.cleaned_data.get("photos") or []:
            DiveLogPhoto.objects.create(log=log, image=image)

    def form_valid(self, form):
        # ログの保存と写真の保存を 1 つの処理にまとめ、途中で失敗したら全部取り消す
        with transaction.atomic():
            response = super().form_valid(form)  # ここで DiveLog が保存され、self.object に入る
            self.save_photos(form)
        return response


class LogCreateView(LoginRequiredMixin, PhotoSaveMixin, CreateView):
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


class LogUpdateView(LoginRequiredMixin, OwnerRequiredMixin, PhotoSaveMixin, UpdateView):
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
        # ログを消すと DiveLogPhoto の行は CASCADE で消えるが、画像ファイルは残るので先に消す
        for photo in self.object.photos.all():
            photo.image.delete(save=False)
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

        # --- 月別潜水本数（潜らなかった月も 0 本として表示する） ---
        monthly = (
            logs.annotate(month=TruncMonth("dive_date"))  # 潜水日を「月の初日」に切り捨てた値を month として付ける
            .values("month")  # month ごとにグループ化する
            .annotate(count=Count("id"))  # グループごとの件数を count として数える
            .order_by("month")  # 月の古い順に並べる
        )
        counts = {(row["month"].year, row["month"].month): row["count"] for row in monthly}  # {(年, 月): 本数} の辞書。DB には潜った月しかない
        first = min(counts)  # 最初に潜った月 (年, 月)
        last = max(counts)  # 最後に潜った月 (年, 月)
        month_labels, month_values = [], []
        year, month = first
        while (year, month) <= last:  # 最初の月から最後の月まで、1か月ずつ進める
            month_labels.append(f"{year}/{month:02d}")  # 横軸のラベル（例: 2026/01）
            month_values.append(counts.get((year, month), 0))  # 辞書にない月（潜っていない月）は 0 本
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)  # 12 月の次は翌年の 1 月
        context["monthly_chart"] = {  # 月別グラフ用のデータ
            "labels": month_labels,
            "values": month_values,
        }

        # --- 潜った場所の地図（ダイビングショップの場所を、潜った場所の目安として使う） ---
        places = {}  # {場所の名前: 地図に出す情報}
        for log in ordered:  # 潜った順に見ていく
            if not log.has_shop_location:  # ショップの場所がないログは地図に出せない
                continue
            place = places.setdefault(log.location or "（場所未入力）", {  # 同じ場所は 1 つの印にまとめる
                "name": log.location or "（場所未入力）",
                "lat": log.dive_shop_lat,
                "lng": log.dive_shop_lng,
                "count": 0,
                "points": [],
                "shops": [],
                "last_date": "",
            })
            place["count"] += 1  # その場所で潜った本数
            if log.dive_point_name and log.dive_point_name not in place["points"]:
                place["points"].append(log.dive_point_name)  # 潜ったポイント（重複なし）
            if log.dive_shop_name and log.dive_shop_name not in place["shops"]:
                place["shops"].append(log.dive_shop_name)  # 利用したショップ（重複なし）
            place["last_date"] = log.dive_date.strftime("%Y/%m/%d")  # 潜った順に上書きするので、最後に潜った日が残る
        context["dive_map"] = sorted(places.values(), key=lambda p: -p["count"])  # 本数の多い順
        context["dive_map_missing"] = sum(1 for log in ordered if not log.has_shop_location)  # 地図に出せなかった本数

        # --- 発見できた魚のワードクラウド（名前ごとの出現回数） ---
        fish_counter = Counter()
        for log in ordered:
            # 半角・全角スペース、カンマ、読点のどれで区切っていても分けられるようにする
            for name in re.split(r"[\s,、，]+", log.fish or ""):
                if name:
                    fish_counter[name] += 1
        context["fish_cloud"] = [[name, count] for name, count in fish_counter.most_common(80)]  # 多い順に最大 80 種類 [名前, 回数]

        # --- ダイブ目的の内訳（DB の値ではなく画面表示用のラベルにする） ---
        purpose_labels = dict(DiveLog.DivePurpose.choices)  # 選択肢を {DB の値: 表示名} の辞書にする
        purposes = logs.values("dive_purpose").annotate(count=Count("id")).order_by("-count")  # 目的ごとの件数を数え、多い順に並べる
        context["purpose_chart"] = {  # 円グラフ用のデータ
            "labels": [str(purpose_labels.get(row["dive_purpose"], row["dive_purpose"])) for row in purposes],  # 目的の表示名（辞書にない値はそのまま表示）
            "values": [row["count"] for row in purposes],  # 目的ごとの本数
        }

        # --- 推移グラフ（1本ごと） ---
        context["trend_chart"] = {  # 推移グラフ用のデータ（どのリストも ordered と同じ順番・同じ件数）
            "labels": [f"{log.dive_date.month}/{log.dive_date.day}" for log in ordered],  # 横軸のラベル（月/日。例: 11/3）
            "months": [log.dive_date.strftime("%Y/%m") for log in ordered],  # 何年何月のダイブか（横軸で月の区切りを表示するのに使う）
            "numbers": list(range(1, len(ordered) + 1)),  # 何本目か（ツールチップに出す）
            "dates": [log.dive_date.strftime("%Y/%m/%d") for log in ordered],  # ツールチップに出す潜水日
            "transparency": [log.transparency for log in ordered],  # 透明度の推移グラフ: 透明度（m）
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