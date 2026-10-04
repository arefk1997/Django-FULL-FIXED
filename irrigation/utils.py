from datetime import date
from .weather_service import WeatherService


def calculate_crop_water_need(plan):
    """
    محاسبه نیاز آبی با استفاده از مرکز ثقل (Centroid) محدوده زمین
    بر اساس فرمول استاندارد FAO-56
    """
    today = date.today()
    days_since_planting = (today - plan.planting_date).days

    if days_since_planting < 0:
        return 0  # اگر هنوز تاریخ کاشت نرسیده باشد

    crop = plan.crop
    kc = 0

    # ۱. منطق انتخاب ضریب گیاهی (Kc) بر اساس مراحل رشد تعریف شده توسط کارشناس
    initial_end = crop.initial_stage_days
    dev_end = initial_end + crop.development_stage_days
    mid_end = dev_end + crop.mid_stage_days

    if days_since_planting <= initial_end:
        kc = crop.kc_initial
    elif days_since_planting <= dev_end:
        # در مرحله توسعه، ضریب گیاهی به تدریج افزایش می‌یابد
        # استفاده از میانگین وزنی ساده برای تخمین Kc در دوره توسعه
        kc = (crop.kc_initial + crop.kc_mid) / 2
    elif days_since_planting <= mid_end:
        kc = crop.kc_mid
    else:
        kc = crop.kc_late

    # ۲. استخراج مختصات جغرافیایی دقیق از فیلد GIS
    if plan.farm.boundary:
        # centroid نقطه هندسی مرکزی مزرعه را برای دقت در هواشناسی برمی‌گرداند
        center_point = plan.farm.boundary.centroid
        lat = center_point.y
        lon = center_point.x
    else:
        # خروجی خطا در صورتی که مرز زمین رسم نشده باشد
        return None

    # ۳. فراخوان سرویس هواشناسی برای دریافت داده‌های لحظه‌ای منطقه
    et0 = WeatherService.get_evapotranspiration(lat, lon)
    rain = WeatherService.get_daily_rain(lat, lon)

    # ۴. محاسبه نهایی: تبخیر گیاه منهای بارش موثر
    if et0 is not None:
        try:
            # فرمول: ETc = ET0 * Kc
            # مقدار بارش مستقیم از نیاز آبی کم می‌شود
            etc = (float(et0) * kc) - float(rain or 0)
            return max(etc, 0)  # مقدار نمی‌تواند منفی باشد
        except (ValueError, TypeError):
            return 5.0  # مقدار پیش‌فرض امن در صورت خطای دیتای API

    return None