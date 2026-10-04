"""
farms/models.py

تغییر اصلی: در Farm.save()، تخصیص خودکار مدیر با فیلدهای role و
managed_regions نوشته شده بود که اصلاً در CustomUser وجود ندارند (مدل واقعی
فیلدهای position و managed_region - تک FK نه M2M - را دارد). این کد با هر
Farm.save() که city داشت و assigned_manager نداشت، FieldError می‌داد و کل
ثبت مزرعه را می‌شکست. اصلاح شد تا از فیلدهای واقعی مدل استفاده کند.
"""
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.conf import settings
from smart_selects.db_fields import ChainedForeignKey
from accounts.models import Region, CustomUser, Company


class Farm(gis_models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='farms',
        verbose_name="سازمان/شرکت مرتبط", null=True, blank=True,
    )
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='farms', verbose_name="کشاورز",
    )
    name = models.CharField(max_length=100, verbose_name="نام مزرعه / قطعه زمین")

    boundary = gis_models.PolygonField(srid=4326, verbose_name="مرز جغرافیایی")
    area_hectares = models.FloatField(verbose_name="مساحت (هکتار)", editable=False, null=True, blank=True)

    province = models.ForeignKey(
        Region, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'level': 3},
        related_name='province_farms', verbose_name="استان",
    )
    city = ChainedForeignKey(
        Region, chained_field="province", chained_model_field="parent",
        show_all=False, auto_choose=True, sort=True,
        null=True, blank=True, on_delete=models.SET_NULL, verbose_name="شهرستان",
    )

    assigned_manager = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_farms', verbose_name="کارشناس مسئول",
    )
    is_approved = models.BooleanField(default=False, verbose_name="وضعیت تایید")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")

    class Meta:
        verbose_name = "مزرعه"
        verbose_name_plural = "مزارع"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.company and self.farmer.company:
            self.company = self.farmer.company

        if self.farmer.chosen_region and (not self.province or not self.city):
            current_reg = self.farmer.chosen_region
            while current_reg:
                if current_reg.level == 3:
                    self.province = current_reg
                elif current_reg.level == 4:
                    self.city = current_reg
                current_reg = current_reg.parent

        if self.boundary:
            try:
                temp_boundary = self.boundary.clone()
                temp_boundary.transform(3857)
                self.area_hectares = round(temp_boundary.area / 10000, 2)
                self.boundary = self.boundary.simplify(0.00001, preserve_topology=True)
            except Exception:
                pass

        # اصلاح شد: role و managed_regions روی CustomUser وجود ندارند.
        # مدل واقعی از position (رشته‌ی choice) و managed_region (FK تکی، نه
        # M2M) استفاده می‌کند. اینجا هر کاربر با سمت 'expert' یا 'group_leader'
        # که مدیریتش دقیقاً همین شهرستان باشد و در همان شرکت باشد، به‌عنوان
        # کارشناس مسئول انتخاب می‌شود. اگر منطق کسب‌وکار شما سمت دیگری
        # می‌خواهد، لیست positions را عوض کنید.
        if self.city and not self.assigned_manager:
            manager = CustomUser.objects.filter(
                position__in=['expert', 'group_leader'],
                managed_region=self.city,
                company=self.company,
                is_active=True,
            ).first()
            if manager:
                self.assigned_manager = manager

        super().save(*args, **kwargs)

    @property
    def centroid_coords(self):
        if self.boundary:
            point = self.boundary.centroid
            return point.y, point.x
        return None, None

    def __str__(self):
        return f"{self.name} ({self.farmer.username})"


class FarmHealthReport(models.Model):
    STATUS_CHOICES = [
        ('good', 'مطلوب'),
        ('warning', 'نیازمند توجه'),
        ('critical', 'بحرانی'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='health_reports', verbose_name="مزرعه")
    report_date = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ گزارش")

    ndvi_value = models.FloatField(verbose_name="شاخص سبزینگی (NDVI)", null=True, blank=True)
    soil_moisture = models.FloatField(verbose_name="رطوبت خاک (%)", null=True, blank=True)
    evapotranspiration = models.FloatField(verbose_name="تبخیر و تعرق (mm)", null=True, blank=True)

    heatmap_image = models.ImageField(upload_to='maps/heatmaps/', null=True, blank=True, verbose_name="تصویر هیت‌مپ")
    legend_data = models.JSONField(null=True, blank=True, verbose_name="دیتای راهنما")

    status_label = models.CharField(max_length=50, choices=STATUS_CHOICES, default='good', verbose_name="وضعیت کلی")
    ai_recommendation = models.TextField(verbose_name="توصیه متخصص/هوش مصنوعی", blank=True)

    class Meta:
        verbose_name = "گزارش سلامت"
        verbose_name_plural = "گزارش‌های سلامت"

    def get_bounds(self):
        if self.farm.boundary:
            ext = self.farm.boundary.extent
            return [[ext[1], ext[0]], [ext[3], ext[2]]]
        return []

    def __str__(self):
        return f"گزارش {self.farm.name} - {self.report_date.strftime('%Y/%m/%d')}"
