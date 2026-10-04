from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django import forms
from django.contrib import messages
from django.http import Http404
from .models import (
    Crop, CropVariety, VariableDefinition, ExpertAnswerSubmission,
    ExpertAnswerDetail, IndicatorDefinition
)


# --- بخش ثبت داده‌های کارشناسی ---

@login_required
def submit_expert_answer(request, crop_id):
    """ثبت پاسخ کارشناس با فرم پویا بر اساس متغیرهای فعال محصول و متصل به چارت سازمانی"""
    user = request.user

    # بررسی سطح دسترسی: پرسنل اداری (به ویژه کارشناسان عملیاتی/staff یا کارشناسان مسئول)
    if user.user_type != 'official':
        messages.error(request, "شما سطح دسترسی لازم برای ثبت داده‌های تخصصی کارشناسی را ندارید.")
        return redirect('dashboard')

    crop = get_object_or_404(Crop, id=crop_id, is_active=True)
    variables = VariableDefinition.objects.filter(crop=crop, is_obsolete=False)

    # تعیین منطقه ثبت پاسخ (اولویت با منطقه مدیریت کارشناس است که باید لایه ۵ یا بالاتر باشد)
    target_region = user.managed_region
    if not target_region:
        messages.error(request, "خطا: قلمرو جغرافیایی و منطقه مدیریت شما در سیستم تعریف نشده است.")
        return redirect('official_dashboard')

    # ایجاد فرم داینامیک شامل انتخاب رقم محصول و متغیرهای عددی
    fields = {}

    # اضافه کردن فیلد انتخاب رقم در صورت وجود ارقام برای این محصول
    varieties = CropVariety.objects.filter(crop=crop)
    if varieties.exists():
        fields['variety'] = forms.ModelChoiceField(
            queryset=varieties,
            label="رقم محصول",
            required=False,
            empty_label="انتخاب رقم محصول (اختیاری)..."
        )

    for var in variables:
        if var.field_type == 'number':
            fields[f'var_{var.id}'] = forms.DecimalField(
                label=var.name,
                required=True,
                max_digits=15,
                decimal_places=3
            )
        else:
            fields[f'var_{var.id}'] = forms.CharField(label=var.name, required=True)

    DynamicForm = type('DynamicExpertForm', (forms.Form,), fields)

    if request.method == 'POST':
        form = DynamicForm(request.POST)
        if form.is_valid():
            # خروج رقم محصول در صورت وجود
            selected_variety = form.cleaned_data.get('variety', None) if 'variety' in form.cleaned_data else None

            # ایجاد سربرگ پاسخ به صورت پیش‌نویس (Draft) جهت هماهنگی با فرآیند تایید تسک‌ها
            submission = ExpertAnswerSubmission.objects.create(
                company=user.company,
                region=target_region,
                crop=crop,
                variety=selected_variety,
                expert=user,
                status='draft'
            )

            # ثبت جزئیات مقادیر عددی متغیرها
            for key, value in form.cleaned_data.items():
                if key == 'variety':
                    continue
                var_id = key.split('_')[1]
                ExpertAnswerDetail.objects.create(
                    submission=submission,
                    variable_id=var_id,
                    value=value
                )

            messages.success(request,
                             f"پیش‌نویس داده‌های محصول {crop.name} با موفقیت ایجاد شد. جهت اعمال در محاسبات، تسک مربوطه را ارسال کنید.")
            return redirect('indicators:crop_list')
    else:
        form = DynamicForm()

    # اعمال کلاس‌های قالب متناسب با استایل‌دهی مدرن سیستم به صورت پویا
    for name, field in form.fields.items():
        field.widget.attrs.update({
            'class': 'w-full px-5 py-4 border-2 border-gray-100 rounded-2xl focus:ring-4 focus:ring-emerald-500/10 focus:border-emerald-500 outline-none transition-all mb-4 text-slate-800 font-bold',
            'placeholder': f'وارد کردن {field.label}...'
        })

    return render(request, 'indicators/submit_form.html', {
        'form': form,
        'crop': crop,
        'variables_count': variables.count(),
        'region': target_region
    })


@login_required
def crop_list(request):
    """لیست محصولات فعال برای شروع فرآیند ثبت داده"""
    if request.user.user_type != 'official':
        return redirect('dashboard')
    crops = Crop.objects.filter(is_active=True).select_related('category')
    return render(request, 'indicators/crop_list.html', {'crops': crops})


# --- بخش مدیریت و تحلیل هوشمند شاخص‌ها ---

@login_required
def manager_indicator_summary(request):
    """نمایش خروجی محاسبات آنی شاخص‌ها با موتور محاسباتی هوشمند"""
    user = request.user

    # تفکیک منطقه بر اساس نوع کاربر برای فیلتر دقیق‌تر محاسبات
    if user.user_type == 'official':
        target_region = user.managed_region
    else:
        target_region = user.chosen_region

    crops = Crop.objects.filter(is_active=True)
    selected_crop_id = request.GET.get('crop')
    indicators_data = []

    if selected_crop_id:
        selected_crop = get_object_or_404(Crop, id=selected_crop_id)
        all_indicators = IndicatorDefinition.objects.all()

        for indicator in all_indicators:
            # فراخوانی متد محاسباتی توکار مدل با استفاده از فیلد متنی path ریجن
            value, status_message = indicator.calculate_smart(region=target_region, crop=selected_crop)

            indicators_data.append({
                'name': indicator.name,
                'unit': indicator.unit,
                'value': value,
                'status': status_message,
                'is_valid': value is not None,
                'bg_color': 'bg-emerald-50 border-emerald-200' if value is not None else 'bg-rose-50 border-rose-100',
                'text_color': 'text-emerald-800' if value is not None else 'text-rose-700'
            })

    return render(request, 'indicators/manager_summary.html', {
        'crops': crops,
        'indicators_data': indicators_data,
        'selected_crop_id': int(selected_crop_id) if selected_crop_id else None,
        'region': target_region
    })


@login_required
def indicator_statistics(request):
    """صفحه گزارشات آماری و نمودارهای بهره‌وری عددی سیستم"""
    return render(request, 'indicators/statistics.html')