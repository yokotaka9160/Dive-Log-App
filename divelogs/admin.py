from django.contrib import admin
from .models import DiveLog

# Register your models here.
@admin.register(DiveLog)
class DiveLogAdmin(admin.ModelAdmin):
# 管理画面の一覧で表示するカラム
    list_display = (
        "calculated_dive_number",
        "dive_date",
        "dive_point_name",
        "location",
        "user",
        "entry_way",
        "dive_purpose",
        "duration_minutes"
    )

    # 絞り込みフィルター
    list_filter = (
        "dive_date",
        "entry_way",
        "dive_purpose",
        "weather",
    )

    # 検索機能の対象フィールド
    search_fields = (
        "dive_point_name",
        "location",
        "buddy_name",
        "fish",
        "free_text_field",
    )

    # 日付による階層表示（ドリルダウンナビゲーション）
    date_hierarchy = "dive_date"