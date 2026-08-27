from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Divelog(models.Model):
    class EntryWay(models.TextChoices):
        BEACH = 'beach', _('ビーチ')  #変数名 = DBに保存される値, 画面に表示される値
        BOAT = 'boat', _('ボート')

    class DivePurpose(models.TextChoices):
        FUN = 'fun', _('ファンダイビング')
        PHOTO = 'photo', _('撮影')
        TRAINING = 'training', _('講習')

    class CurrentStrength(models.TextChoices):
        NONE = 'none', _('なし')
        WEAK = 'weak', _('弱い')
        STRONG = 'strong', _('強い')

    class Weather(models.TextChoices):
        SUNNY = 'sunny', _('晴れ')
        CLOUDY = 'cloudy', _('曇り')
        RAINY = 'rainy', _('雨')

    class WaveHeight(models.TextChoices):
        NONE = 'none', _('無し')
        LOW = 'low', _('低')
        MIDDLE = 'middle', _('中')
        HIGH = 'high', _('高')

    class TankType(models.TextChoices):
        STEEL = 'steel',_('スチール')
        ALMI = 'almi',_('アルミニウム')
        
    class WindStrength(models.TextChoices):
        NONE = 'none', _('無し')
        LOW = 'low', _('弱')
        MIDDLE = 'middle', _('中')
        HIGH = 'high', _('強')

    author = models.ForeignKey( #「1人のUserが、複数のArticleを投稿できる」という関係の定義
        User, #ForeignKeyの第一引数 で、「どのモデルを参照するか」
        on_delete=models.CASCADE, #参照先( User )のレコードが削除されたときの挙動を指定(親が消えたら子も連動して削除する)
        related_name='dive_logs', #逆参照名（user.dive_logでユーザのダイブログを参照できるようになる設定）
        verbose_name=_("ダイバー") #管理画面やフォームで表示される ラベル文字列 を指定
    )
    dive_date = models.DateField(
        verbose_name=_("潜水日付")
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("場所")
    )
    dive_point_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("ポイント名")
    )
    entry_way = models.CharField(
        max_length=20,
        choices=EntryWay.choices,
        verbose_name=_("エントリー方法")
    )
    dive_purpose = models.CharField(
        max_length=20,
        choices=DivePurpose.choices,
        verbose_name=_("ダイブ目的")
    )
    entry_date = models.DateTimeField(
        verbose_name=_("エントリー日時")
    )
    exit_date = models.DateTimeField(
        verbose_name=_("エキジット日時")
    )
    start_press = models.IntegerField(
        verbose_name=_("潜水開始時タンク圧力")
    )
    end_press = models.IntegerField(
        verbose_name=_("潜水終了時タンク圧力")
    )
    tank_type = models.CharField(
        max_length=20,
        choices=TankType.choices,
        verbose_name=_("タンク種別")
    )
    weight = models.IntegerField(
        verbose_name=_("ウェイト重量")
    )
    current_str = models.CharField(
        max_length=20,
        choices=CurrentStrength.choices,
        verbose_name=_("流れの強さ")
    )
    weather = models.CharField(
        max_length=20,
        choices=Weather.choices,
        verbose_name=_("天気")
    )
    wave_height = models.CharField(
        max_length=20,
        choices=WaveHeight.choices,
        verbose_name=_("波の高さ")
    )
    wind_speed = models.CharField(
        max_length=20,
        choices=WindStrength.choices,
        verbose_name=_("風の強さ")
    )
    temperature = models.FloatField(
        verbose_name=_("気温")
    )
    surf_temp = models.FloatField(
        verbose_name=_("水面温度")
    )
    w_bottom_temp = models.FloatField(
        verbose_name=_("水底温度")
    )
    transparency = models.IntegerField(
        verbose_name=_("透明度")
    )
    buddy_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("バディ名")
    )
    inst_name = models.CharField(
        max_length=100,
        blank=True, #フォーム入力時に空欄を許可する
        verbose_name=_("インストラクター名")
    )
    fish = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("発見できた魚")
    )
    free_text_field = models.TextField(
        blank=True,
        verbose_name=_("自由記述欄")
    )
    #DiveLogモデルの設定
    class Meta:
        verbose_name = _("ダイブログ")#管理画面などで表示される、このモデルの「単数形」の名前
        verbose_name_plural = _("ダイブログ")#管理画面などで表示される、このモデルの「複数形」の名前
        ordering = ['-dive_date'] # このモデルのデータを取得したときの デフォルトの並び順 
    #DiveLogモデルを文字列として表示する時の返り値
    def __str__(self):
        return f"{self.dive_date} - {self.dive_point_name}"