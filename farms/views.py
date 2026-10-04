"""
farms/views.py

تغییرات:
- @allowed_users(allowed_positions=['farmer']) با @farmer_required جایگزین شد.
  دلیل: CustomUser.save() فیلد position را برای کشاورزان همیشه None می‌کند،
  پس شرط قبلی هیچ‌وقت True نمی‌شد و هیچ کشاورزی به این صفحات نمی‌رسید.
- request.user.province / request.user.city حذف شدند؛ این فیلدها روی
  CustomUser وجود ندارند (getattr همیشه None برمی‌گرداند و کد را گمراه‌کننده
  می‌کرد). استان/شهر واقعی از طریق Farm.save() و زنجیره‌ی chosen_region
  محاسبه می‌شود؛ اینجا فقط برای نمایش، از chosen_region کاربر استفاده شده.
"""
import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import farmer_required
from .models import Farm

logger = logging.getLogger(__name__)


@login_required
@farmer_required
def add_farm_view(request):
    """نمای ثبت مزرعه جدید - منطقه به صورت خودکار از پروفایل کاربر برداشته می‌شود."""
    if request.method == 'POST':
        name = request.POST.get('name')
        boundary_json = request.POST.get('boundary_data')

        if boundary_json and name:
            try:
                poly_dict = json.loads(boundary_json)
                boundary_geom = GEOSGeometry(json.dumps(poly_dict))

                new_farm = Farm.objects.create(
                    farmer=request.user,
                    name=name,
                    boundary=boundary_geom,
                    # province/city دیگر مستقیم اینجا ست نمی‌شوند؛ Farm.save()
                    # آن‌ها را از chosen_region کشاورز به‌صورت خودکار پر می‌کند.
                )

                messages.success(
                    request,
                    f"مزرعه '{name}' با موفقیت در محدوده "
                    f"{new_farm.city.name if new_farm.city else 'منطقه شما'} ثبت شد.",
                )
                return redirect('farms:farm_list')

            except (json.JSONDecodeError, GEOSException) as e:
                logger.warning("خطای پردازش نقشه برای کاربر %s: %s", request.user.id, e)
                messages.error(request, "خطا در پردازش نقشه. لطفاً محدوده را دوباره روی نقشه رسم کنید.")
        else:
            messages.warning(request, "لطفاً نام مزرعه را وارد کرده و محدوده آن را روی نقشه رسم کنید.")

    context = {
        'user_region': {
            'province': request.user.chosen_region.parent.parent
            if request.user.chosen_region and request.user.chosen_region.level == 5 else None,
            'city': request.user.chosen_region.parent
            if request.user.chosen_region and request.user.chosen_region.level == 5 else None,
        }
    }
    return render(request, 'farms/add_farm.html', context)


@login_required
def farm_list_view(request):
    """نمایش لیست تمام مزارع ثبت شده توسط کاربر."""
    farms = Farm.objects.filter(farmer=request.user).order_by('-created_at')
    return render(request, 'farms/farm_list.html', {'farms': farms})


@login_required
@farmer_required
def farm_health_detail(request, farm_id):
    """جزئیات پایش ماهواره‌ای یک مزرعه خاص."""
    farm = get_object_or_404(Farm, id=farm_id, farmer=request.user)
    latest_report = farm.health_reports.order_by('-report_date').first()

    return render(request, 'farms/health_report.html', {
        'farm': farm,
        'report': latest_report,
    })
