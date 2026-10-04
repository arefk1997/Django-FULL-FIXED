# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import CustomUser, Region


class CustomUserCreationForm(UserCreationForm):
    """
    فرم ثبت‌نام زنجیره‌ای و هوشمند کشاورزان (بهره‌برداران)
    سلسله مراتب: استان (سطح ۳) -> شهرستان (سطح ۴) -> بخش / واحد کارشناسی (سطح ۵)
    """
    province = forms.ModelChoiceField(
        queryset=Region.objects.filter(level=3),
        label="📍 انتخاب استان",
        empty_label="استان را انتخاب کنید...",
        required=True
    )

    city = forms.ModelChoiceField(
        queryset=Region.objects.none(),
        label="🏛 انتخاب شهرستان",
        empty_label="ابتدا استان را انتخاب کنید",
        required=True
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "first_name", "last_name", "phone_number", "national_code", "chosen_region")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # تنظیم اولیه فیلد بخش (مقصد پایانی کشاورز در سطح ۵)
        self.fields['chosen_region'].queryset = Region.objects.none()
        self.fields['chosen_region'].label = "🌱 بخش / واحد کارشناسی"
        self.fields['chosen_region'].empty_label = "ابتدا شهرستان را انتخاب کنید"
        self.fields['chosen_region'].required = True

        # منطق پویای همگام‌سازی داده‌های فرستاده شده با درخواست Ajax
        data = self.data if self.is_bound else self.initial
        if 'province' in data:
            try:
                province_id = int(data.get('province'))
                self.fields['city'].queryset = Region.objects.filter(parent_id=province_id, level=4)
            except (ValueError, TypeError):
                pass

        if 'city' in data:
            try:
                city_id = int(data.get('city'))
                self.fields['chosen_region'].queryset = Region.objects.filter(parent_id=city_id, level=5)
            except (ValueError, TypeError):
                pass

        # اعمال اتوماتیک کلاس استایل‌دهی پریمیوم Tailwind CSS
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 mb-2 transition-all font-bold text-xs text-slate-700 bg-slate-50',
            })

    def clean_national_code(self):
        nc = self.cleaned_data.get('national_code')
        if nc and (len(nc) != 10 or not nc.isdigit()):
            raise ValidationError("کد ملی وارد شده نامعتبر است؛ باید دقیقاً شامل ۱۰ رقم باشد.")
        return nc

    def clean(self):
        cleaned_data = super().clean()
        province = cleaned_data.get('province')
        city = cleaned_data.get('city')
        chosen_region = cleaned_data.get('chosen_region')

        if city and province and city.parent != province:
            raise ValidationError("شهرستان انتخاب شده با استان مطابقت ندارد.")
        if chosen_region and city and chosen_region.parent != city:
            raise ValidationError("بخش انتخاب شده با شهرستان مطابقت ندارد.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'farmer'
        user.is_approved = False

        # توجه: بر اساس متد save در مدل شما، فیلدهای position و office_level برای کشاورز None می‌شوند.
        # پس دیگر مقداردهی متنی برای آن‌ها انجام نمی‌دهیم تا دیتابیس پایدار بماند.
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """فرم ویرایش ساختار کاربران در پنل مدیریت ادمین جنگو"""

    class Meta:
        model = CustomUser
        fields = (
            'username', 'email', 'phone_number', 'national_code',
            'user_type', 'position', 'office_level', 'company',
            'is_approved', 'is_active', 'chosen_region', 'managed_region'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'chosen_region' in self.fields:
            self.fields['chosen_region'].queryset = Region.objects.filter(level=5)
        if 'managed_region' in self.fields:
            self.fields['managed_region'].queryset = Region.objects.filter(level__in=[1, 2, 3, 4, 5])

        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-xs font-bold'
                })