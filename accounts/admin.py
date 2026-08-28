# Django の管理画面機能そのものを使うためのモジュールをインポート
from django.contrib import admin
# Django が標準で用意している「ユーザー管理用の管理画面クラス」をインポート
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
# accounts/models.py で定義したカスタム User モデルをインポート(管理画面に登録するため)
from .models import User


class UserAdmin(DjangoUserAdmin):
    """カスタムUserモデル用の管理画面設定"""

    # ユーザー一覧画面に表示する項目を指定
    list_display = ("email", "username", "is_staff", "is_active", "date_joined")

    # 一覧画面の右側に表示される絞り込みフィルターの項目
    list_filter = ("is_staff", "is_active")

    # 既存ユーザーの編集画面で表示するフィールドをグループ分けして指定
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("権限", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("重要な日付", {"fields": ("last_login", "date_joined")}),
    )

    # 新規ユーザー作成画面で表示するフィールドを指定（編集画面とは別に定義が必要)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )

    # 一覧画面の検索ボックスで検索対象にするフィールド
    search_fields = ("email", "username")

    # 一覧画面での並び順を指定するフィールド
    ordering = ("email",)


admin.site.register(User, UserAdmin)