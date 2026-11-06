from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import DiveLog

User = get_user_model()

class SignUpForm(UserCreationForm):
    """メールアドレス任意のユーザー登録フォーム。"""

    email = forms.EmailField(label="メールアドレス", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class DiveLogForm(forms.ModelForm):
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