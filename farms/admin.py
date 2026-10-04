from django.contrib import admin
from django.contrib.gis import admin as gis_admin
from .models import Farm, FarmHealthReport
from accounts.models import Region


@admin.register(Farm)
class FarmAdmin(gis_admin.GISModelAdmin):
    # ۱. تنظیمات نمایش در لیست اصلی ادمین
    list_display = ('name', 'farmer', 'province', 'city', 'assigned_manager', 'is_approved', 'area_hectares')
    list_filter = ('is_approved', 'province', 'created_at')
    search_fields = ('name', 'farmer__username', 'city__name')

    # ۲. فیلدهایی که فقط خواندنی هستند
    readonly_fields = ('area_hectares', 'assigned_manager', 'created_at')

    # ۳. تنظیمات نقشه اختصاصی پنل مدیریت (OpenStreetMap)
    # استفاده از لایه OSM برای بارگذاری سریع‌تر و پایدارتر در ایران
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 11,
            'default_lat': 31.89,  # مختصات پیش‌فرض (مثلاً مرکز خوزستان یا ایران)
            'default_lon': 48.67,
            'map_height': 500,
            'display_raw': False,
        }
    }

    # ۴. چیدمان فیلدها
    fieldsets = (
        ('اطلاعات مالکیت و تایید', {
            'fields': ('farmer', 'name', 'assigned_manager', 'is_approved')
        }),
        ('موقعیت جغرافیایی اداری', {
            'fields': ('province', 'city'),
            'description': 'با انتخاب شهرستان، کارشناس مسئول به صورت خودکار تخصیص می‌یابد.'
        }),
        ('ترسیم فنی مرز اراضی', {
            'fields': ('boundary', 'area_hectares'),
            'description': 'از ابزار ترسیم بالای نقشه برای مشخص کردن پولیگون زمین استفاده کنید.'
        }),
        ('تاریخچه‌ سیستم', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """کنترل سطح دسترسی: هر نقش فقط داده‌های مربوط به خود را می‌بیند"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        # اگر کاربر مدیر منطقه (کارشناس) باشد
        if hasattr(request.user, 'role') and request.user.role == 'region_manager':
            return qs.filter(assigned_manager=request.user)

        # اگر کاربر کشاورز باشد (در صورتی که به ادمین دسترسی داشته باشد)
        if hasattr(request.user, 'role') and request.user.role == 'farmer':
            return qs.filter(farmer=request.user)

        return qs

    def save_model(self, request, obj, form, change):
        """اعمال منطق‌های خودکار قبل از ذخیره نهایی"""
        # اگر کشاورز خودش در حال ثبت است
        if not request.user.is_superuser and not change:
            obj.farmer = request.user

        # توجه: محاسبات مساحت و تعیین مدیر در متد save خود مدل انجام می‌شود
        super().save_model(request, obj, form, change)


# ۵. ثبت مدل گزارش سلامت برای مدیریت داده‌های ماهواره‌ای در ادمین
@admin.register(FarmHealthReport)
class FarmHealthReportAdmin(admin.ModelAdmin):
    list_display = ('farm', 'report_date', 'status_label', 'ndvi_value', 'soil_moisture')
    list_filter = ('status_label', 'report_date')
    readonly_fields = ('report_date',)