from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Max, Q
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

from .forms import DiveLogForm, SignUpForm
from .models import DiveLog

# 並び替えの選択肢: キー -> (ラベル, order_by 引数)
SORT_OPTIONS = {
    "new": ("新しい順", ["-dive_date","-id"]),
    "old": ("古い順", ["dive_date","id"]),
    "depth": ("深度が深い順", ["-max_depth"]),
    "duration": ("潜水時間が長い順", ["-duration"]),
    # "popular": ("お気に入りが多い順", ["-fav_total", "-date"]),
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
        qs = DiveLog.objects.select_related("user")

        # 検索
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(site__icontains=query)
                | Q(location__icontains=query)
                | Q(creatures__icontains=query)
                | Q(notes__icontains=query)
            )

        # お気に入り絞り込み（ログイン時のみ有効）
        # if self.request.GET.get("fav") == "1" and self.request.user.is_authenticated:
        #     qs = qs.filter(favorites=self.request.user)

        # 自分の投稿のみ
        if self.request.GET.get("mine") == "1" and self.request.user.is_authenticated:
            qs = qs.filter(user=self.request.user)

        # 並び替え
        sort = self.request.GET.get("sort", "new")
        order = SORT_OPTIONS.get(sort, SORT_OPTIONS["new"])[1]
        return qs.order_by(*order)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.request.GET.get("q", "")
        ctx["mine_only"] = self.request.GET.get("mine") == "1"
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


# @login_required
# def toggle_favorite(request, pk):
#     """お気に入りの登録/解除。"""
#     if request.method != "POST":
#         return redirect("log_detail", pk=pk)
#     log = get_object_or_404(DiveLog, pk=pk)
#     if log.favorites.filter(pk=request.user.pk).exists():
#         log.favorites.remove(request.user)
#     else:
#         log.favorites.add(request.user)
#     next_url = request.POST.get("next") or log.get_absolute_url()
#     return redirect(next_url)


def signup(request):
    if request.user.is_authenticated:
        return redirect("log_list")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "ようこそ、DEEPLOG へ。")
            return redirect("log_list")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "logs/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logs = DiveLog.objects.filter(user=self.request.user)

        # 推移グラフは潜った順（エントリー日時の古い順）に並べる
        ordered = list(logs.order_by("entry_date", "id"))
        context["total_logs"] = len(ordered)
        if not ordered:
            return context

        # --- 数値サマリー ---
        durations = [log.duration_minutes for log in ordered if log.duration_minutes is not None]
        context["total_minutes"] = sum(durations)
        stats = logs.aggregate(max_depth=Max("max_depth"), max_ave_depth=Max("ave_depth"))
        context["max_depth"] = stats["max_depth"]
        context["max_ave_depth"] = stats["max_ave_depth"]

        # --- 月別潜水本数 ---
        monthly = (
            logs.annotate(month=TruncMonth("dive_date"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        context["monthly_chart"] = {
            "labels": [row["month"].strftime("%Y/%m") for row in monthly],
            "values": [row["count"] for row in monthly],
        }

        # --- ダイブ目的の内訳（DB の値ではなく画面表示用のラベルにする） ---
        purpose_labels = dict(DiveLog.DivePurpose.choices)
        purposes = logs.values("dive_purpose").annotate(count=Count("id")).order_by("-count")
        context["purpose_chart"] = {
            "labels": [str(purpose_labels.get(row["dive_purpose"], row["dive_purpose"])) for row in purposes],
            "values": [row["count"] for row in purposes],
        }

        # --- 推移グラフ（1本ごと） ---
        context["trend_chart"] = {
            "labels": [f"{i}本目" for i in range(1, len(ordered) + 1)],
            "dates": [log.dive_date.strftime("%Y/%m/%d") for log in ordered],
            "pressure_used": [log.start_press - log.end_press for log in ordered],
            "max_depth": [log.max_depth for log in ordered],
            "ave_depth": [log.ave_depth for log in ordered],
            "duration": [log.duration_minutes for log in ordered],
            "bottom_temp": [log.w_bottom_temp for log in ordered],
        }
        return context