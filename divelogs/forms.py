from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import DiveLog

User = get_user_model()

MAX_PHOTO_BYTES = 10 * 1024 * 1024   # 1枚の上限（10MB）
MAX_PHOTOS = 10                      # 1つのログの写真の上限

class MultipleFileInput(forms.ClearableFileInput):
        allow_multiple_selected = True

class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file(d, initial) for d in data]
        return single_file(data, initial)
        
class DiveLogForm(forms.ModelForm):
    
    photos = MultipleImageField(
    required=False,
    widget=MultipleFileInput(attrs={"accept": "image/*"}),
    label="写真",
    )

    class Meta:
        model = DiveLog
        fields = [
            "dive_date",
            "location",
            "dive_point_name",
            "entry_way",
            "dive_purpose",
            "entry_date",
            "exit_date",
            "start_press",
            "end_press",
            "tank_type",
            "weight",
            "current_str",
            "weather",
            "wave_height",
            "wind_speed",
            "temperature",
            "surf_temp",
            "w_bottom_temp",
            "ave_depth",
            "max_depth",
            "transparency",
            "buddy_name",
            "inst_name",
            "fish",
            "free_text_field",
            "suit_type",
        ]
        widgets = {
            "dive_date": forms.DateInput(attrs={"type": "date"}),
            "entry_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "exit_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "free_text_field": forms.Textarea(attrs={"rows": 5}),
            "fish": forms.TextInput(
                attrs={"placeholder": "例: マンタ, ウミガメ, カクレクマノミ"}
            ),
        }

    def clean_photos(self):
        photos = self.cleaned_data.get("photos") or []
        for photo in photos:
            if photo.size > MAX_PHOTO_BYTES:
                raise forms.ValidationError(
                    f"1枚の写真のサイズは10MB以下にしてください。{photo.name}は{photo.size / (1024 * 1024):.2f}MBです。"
                )
        return photos

def with_all(choices):
    """全ての選択肢を含むタプルを返す。"""
    return [("", "全て")]+ list(choices)

class DiveLogFilterForm(forms.Form):
    """マイログの絞り込みフォーム。すべて任意入力（空欄なら、その条件では絞り込まない）"""

    q = forms.CharField(
        required=False, 
        label="検索", 
        widget=forms.TextInput(attrs={
            "type": "search",
            "placeholder": "場所・ポイント名・生物名など"
            }),
        )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    entry_way = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.EntryWay.choices),
        label="エントリー方法",
    )

    depth_min = forms.FloatField(required=False,min_value=0, label="最小水深(m)")
    depth_max = forms.FloatField(required=False,min_value=0, label="最大水深(m)")

    dive_purpose = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.DivePurpose.choices),
        label="ダイビング目的",
    )

    weather = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.Weather.choices),
        label="天気",
    )

    current_str = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.CurrentStrength.choices),
        label="流れの強さ",
    )   

    tank_type = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.TankType.choices),
        label="タンク種別",
    )

    suit_type = forms.ChoiceField(
        required=False,
        choices=with_all(DiveLog.SuitType.choices),
        label="スーツ種別",
    )

    transparency_min = forms.IntegerField(required=False, min_value=0, label="最小透明度(m)")

    transparency_max = forms.IntegerField(required=False, min_value=0, label="最大透明度(m)")

    duration_min = forms.IntegerField(required=False, min_value=0, label="潜水時間(分)")

    bottom_temp_min = forms.FloatField(required=False, label="最小水温(℃)")

    bottom_temp_max = forms.FloatField(required=False, label="最大水温(℃)")






    
