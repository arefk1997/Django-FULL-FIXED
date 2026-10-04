"""
irrigation/views.py

تغییرات:
- calculate_crop_water_need(plan) قبلاً هم در حلقه‌ی گذشته (بدون سقف) و هم
  در حلقه‌ی ۳۰ روز آینده، هر بار جداگانه صدا زده می‌شد. اگر این تابع به یک
  API هواشناسی خارجی وصل باشد (که در weather_service.py همین‌طور است، با
  timeout=5 ثانیه)، این صفحه می‌توانست صدها درخواست HTTP بزند و چند دقیقه
  طول بکشد یا کامل تایم‌اوت شود.
  چون این تابع مقدار ثابتی برای یک plan مشخص برمی‌گرداند (پارامترهای صدا زدن
  عوض نمی‌شوند)، همین یک بار محاسبه و در طول تابع cache می‌شود.
- حلقه‌ی `while temp_date < today` قبلاً هیچ سقفی نداشت؛ اگر start_calculation_from
  به هر دلیلی (باگ داده یا مقدار پیش‌فرض اشتباه) خیلی قدیمی باشد، این حلقه
  می‌توانست میلیون‌ها بار اجرا شود و درخواست را کاملاً hang کند. یک سقف منطقی
  (مثلاً ۹۰ روز) اضافه شد.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import IrrigationPlan
from .utils import calculate_crop_water_need
from datetime import date, timedelta

MAX_BACKFILL_DAYS = 90  # سقف منطقی برای محاسبه‌ی کمبود آب گذشته


@login_required
def irrigation_calendar_view(request):
    """نمایش تقویم ۳۰ روزه پیش‌بینی آبیاری."""
    plan = IrrigationPlan.objects.filter(farmer=request.user).select_related('crop', 'farm').last()

    if not plan:
        return render(request, 'irrigation/no_plan.html')

    # محاسبه‌ی نیاز آبی روزانه فقط یک بار انجام می‌شود (نه یک بار به ازای هر
    # روز)، چون ورودی‌های calculate_crop_water_need در طول این تابع تغییر
    # نمی‌کنند.
    daily_water_need = calculate_crop_water_need(plan) or 5.0

    calendar_data = []
    max_depletion = plan.crop.max_soil_moisture_depletion
    today = date.today()

    base_date = plan.start_calculation_from
    current_deficit = 0

    temp_date = base_date
    days_processed = 0
    while temp_date < today and days_processed < MAX_BACKFILL_DAYS:
        current_deficit += daily_water_need
        temp_date += timedelta(days=1)
        days_processed += 1

    cumulative_deficit = current_deficit

    for i in range(30):
        current_date = today + timedelta(days=i)
        cumulative_deficit += daily_water_need

        should_irrigate = False
        if cumulative_deficit >= max_depletion:
            should_irrigate = True
            cumulative_deficit = 0

        calendar_data.append({
            'date': current_date,
            'need': round(daily_water_need, 1),
            'should_irrigate': should_irrigate,
        })

    context = {
        'plan': plan,
        'calendar_data': calendar_data,
        'today': today,
        'last_watered': plan.last_irrigation_date,
    }
    return render(request, 'irrigation/calendar.html', context)


@login_required
@require_POST
def record_irrigation(request, plan_id):
    """ثبت فیدبک واقعی کشاورز مبنی بر انجام آبیاری."""
    plan = get_object_or_404(IrrigationPlan, id=plan_id, farmer=request.user)
    plan.last_irrigation_date = date.today()
    plan.save()
    messages.success(request, "عملیات آبیاری با موفقیت در سیستم ثبت شد. تقویم شما بازنشانی گردید.")
    return redirect('irrigation_calendar')
