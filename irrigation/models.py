from django.db import models
from django.conf import settings
from accounts.models import Region


# ۱. جدول پارامترهای گیاهی که توسط کارشناس منطقه (لایه ۵) پر می‌شود
class CropFactor(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, verbose_name="منطقه (بخش)")
    name = models.CharField(max_length=100, verbose_name="نام محصول")

    # مراحل رشد بر اساس استاندارد FAO-56
    initial_stage_days = models.IntegerField(verbose_name="طول دوره ابتدایی (روز)")
    development_stage_days = models.IntegerField(verbose_name="طول دوره توسعه (روز)")
    mid_stage_days = models.IntegerField(verbose_name="طول دوره میانی (روز)")
    late_stage_days = models.IntegerField(verbose_name="طول دوره انتهایی (روز)")

    # ضرایب گیاهی (Crop Coefficients)
    kc_initial = models.FloatField(verbose_name="ضریب ابتدایی (Kc Initial)")
    kc_mid = models.FloatField(verbose_name="ضریب میانی (Kc Mid)")
    kc_late = models.FloatField(verbose_name="ضریب انتهایی (Kc Late)")

    # پارامتر مدیریت رطوبت خاک
    max_soil_moisture_depletion = models.FloatField(
        default=30.0,
        verbose_name="حد مجاز تخلیه رطوبت (میلی‌متر)",
        help_text="زمانی که تبخیر تجمعی به این عدد رسید، سیستم پیشنهاد آبیاری می‌دهد"
    )

    class Meta:
        verbose_name = "ضریب گیاهی"
        verbose_name_plural = "ضریب‌های گیاهی"

    def __str__(self):
        return f"{self.name} - {self.region.name}"


# ۲. برنامه آبیاری شخصی بهره‌بردار (کشاورز)
class IrrigationPlan(models.Model):
    IRRIGATION_METHODS = [
        ('surface', 'غرقابی'),
        ('drip', 'قطره‌ای'),
        ('sprinkler', 'بارانی'),
    ]

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='irrigation_plans'
    )
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.CASCADE,
        related_name='irrigation_plans'
    )
    crop = models.ForeignKey(
        CropFactor,
        on_delete=models.PROTECT,
        verbose_name="محصول و منطقه"
    )
    planting_date = models.DateField(verbose_name="تاریخ کاشت")
    area_hectares = models.FloatField(verbose_name="مساحت زیر کشت (هکتار)")
    irrigation_method = models.CharField(
        max_length=50,
        choices=IRRIGATION_METHODS,
        default='surface',
        verbose_name="روش آبیاری"
    )

    # فیلد کلیدی برای همگام‌سازی با واقعیت مزرعه
    last_irrigation_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="تاریخ آخرین آبیاری واقعی",
        help_text="آخرین زمانی که کشاورز دکمه تایید آبیاری را زده است"
    )

    class Meta:
        verbose_name = "برنامه آبیاری"
        verbose_name_plural = "برنامه‌های آبیاری"

    def __str__(self):
        return f"برنامه {self.crop.name} برای مزرعه {self.farm.name}"

    @property
    def start_calculation_from(self):
        """تعیین مبدا زمانی برای شروع محاسبات تبخیر تجمعی"""
        return self.last_irrigation_date or self.planting_date