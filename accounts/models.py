from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Djangoの標準Userを拡張したカスタムユーザーモデル。
    username, email, password は AbstractUser に定義済み。
    """

    class DiverRank(models.TextChoices):
        NoRank = 'no_rank', _('ランクなし')
        OpenWater = 'OW', _('オープンウォータ―')
        AdvancedOW = 'AOW', _('アドバンスドオープンウォータ―')
        Rescue = 'RED', _('レスキュー')
        DiveMaster = 'DM', _('ダイブマスター')

    email = models.EmailField(
        unique=True,
        verbose_name=_("メールアドレス")
    )
    nickname = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("ニックネーム")
    )
    diver_rank = models.CharField(
        max_length=20,
        choices=DiverRank.choices,
        default=DiverRank.NoRank,
        verbose_name=_("ダイバーランク")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("作成日時")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("更新日時")
    )

    class Meta:
        verbose_name = _("ユーザー")
        verbose_name_plural = _("ユーザー")

    def __str__(self):
        return self.nickname or self.username

    @property
    def dive_nums(self):
        """このユーザーが投稿したダイブログの件数"""
        return self.dive_logs.count()
