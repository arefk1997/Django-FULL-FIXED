from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from django.utils.safestring import mark_safe
from .models import (
    CropCategory, CropFamily, Crop, CropVariety, IndicatorDefinition,
    VariableDefinition, ExpertAnswerSubmission, ExpertAnswerDetail
)


# ۰. مدیریت دسته‌بندی‌های کلان
@admin.register(CropCategory)
class CropCategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)  # مورد نیاز برای فیلدهای autocomplete سایر مدل‌ها
    list_display = ('name', 'icon', 'crop_count')

    def crop_count(self, obj):
        return obj.crops.count()

    crop_count.short_description = "تعداد محصولات"


# ۰.۱. مدیریت خانواده‌های گیاهی
@admin.register(CropFamily)
class CropFamilyAdmin(admin.ModelAdmin):
    search_fields = ('name',)  # مورد نیاز برای فیلدهای autocomplete سایر مدل‌ها
    list_display = ('name', 'crop_count')

    def crop_count(self, obj):
        return obj.crops.count()

    crop_count.short_description = "تعداد محصولات این خانواده"


# ۰.۲. مدیریت واریته‌های محصول (حل قطعی خطای سیستم چک جنگو admin.E039)
@admin.register(CropVariety)
class CropVarietyAdmin(admin.ModelAdmin):
    search_fields = ('name', 'crop__name')  # فیلد جستجوی اجباری برای فعال شدن autocomplete_fields
    list_display = ('name', 'crop', 'description')
    list_filter = ('crop',)


# ۱. اینلاین‌ها برای صفحه محصول
class VariableDefinitionInline(admin.TabularInline):
    model = VariableDefinition
    extra = 1
    fields = ('code', 'name', 'activity', 'field_type', 'target_indicator', 'order', 'is_obsolete')
    readonly_fields = ('code',)
    ordering = ('order',)


class CropVarietyInline(admin.TabularInline):
    model = CropVariety
    extra = 2
    fields = ('name', 'description')


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    search_fields = ('name', 'slug', 'category__name', 'family__name')  # فیلد جستجوی ریشه محصول
    list_display = ('name', 'slug', 'category', 'family', 'is_active', 'variable_count')
    list_editable = ('category', 'family', 'is_active')
    list_filter = ('category', 'family', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [VariableDefinitionInline, CropVarietyInline]

    def variable_count(self, obj):
        return obj.variables.count()

    variable_count.short_description = "تعداد سوالات"


@admin.register(IndicatorDefinition)
class IndicatorDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'calculation_level', 'scope', 'unit', 'formula_display')
    list_filter = ('calculation_level', 'scope', 'target_category')
    search_fields = ('name', 'formula')

    fieldsets = (
        ("تعریف پایه شاخص", {
            'fields': ('name', 'unit', 'formula'),
            'description': mark_safe(
                '<div style="background: #eff6ff; padding: 10px; border-right: 4px solid #3b82f6; color: #1e40af; font-size: 0.85rem;">'
                '<strong>راهنمای فرمول‌نویسی پیشرفته:</strong><br>'
                '• برای نرمال‌سازی: <code>yield / yield_max</code><br>'
                '• فرمول شرطی: <code>(yield * 1.1) if yield > 5 else (yield * 0.9)</code><br>'
                '• توابع ریاضی: <code>math.sqrt(yield)</code> یا <code>yield ** 2</code><br>'
                '• عملگرهای مجاز: <code>+ - * / **</code> و پرانتز <code>()</code>'
                '</div>'
            )
        }),
        ("تنظیمات استراتژیک (سطح و دامنه)", {
            'fields': ('calculation_level', 'scope', 'target_category'),
        }),
    )

    def formula_display(self, obj):
        if obj.formula:
            return format_html(
                '<code style="background: #fdf2f8; color: #be185d; padding: 3px 8px; border-radius: 6px; border: 1px solid #fbcfe8; font-family: monospace; font-weight: bold;">{}</code>',
                obj.formula
            )
        return "-"

    formula_display.short_description = "فرمول محاسباتی"


@admin.register(VariableDefinition)
class VariableDefinitionAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code', 'crop__name', 'activity__title')
    list_display = ('code', 'name', 'crop', 'activity', 'target_indicator', 'is_obsolete', 'order')
    list_filter = ('crop', 'activity', 'target_indicator', 'is_obsolete')
    list_editable = ('order', 'is_obsolete')
    ordering = ('crop', 'order')


# ۲. مدیریت پاسخ‌های کارشناسان
class ExpertAnswerDetailInline(admin.TabularInline):
    model = ExpertAnswerDetail
    extra = 0
    can_delete = False
    fields = ('variable', 'value')

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == 'verified':
            return ('variable', 'value')
        return ('variable',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ExpertAnswerSubmission)
class ExpertAnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ('crop_icon', 'crop', 'variety', 'region', 'expert', 'colored_status', 'created_at')
    list_filter = ('status', 'crop__category', 'crop__family', 'crop', 'created_at')
    search_fields = ('region__name', 'crop__name', 'variety__name', 'expert__username')

    # همگی مدل‌های داخل این لیست اکنون مجهز به ثبت‌نام ادمین و search_fields معتبر هستند
    autocomplete_fields = ['region', 'expert', 'company', 'crop', 'variety']
    inlines = [ExpertAnswerDetailInline]
    actions = ['make_verified']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('created_at', 'updated_at', 'expert', 'company', 'region', 'crop', 'variety')
        return ('created_at', 'updated_at')

    @admin.action(description='تایید نهایی موارد انتخاب شده و فعال‌سازی در موتور محاسباتی')
    def make_verified(self, request, queryset):
        queryset.update(status='verified')
        self.message_user(request,
                          "موارد انتخاب شده تغییر وضعیت داده و جهت استفاده در محاسبات هوشمند شاخص‌ها فعال شدند.")

    def crop_icon(self, obj):
        # جلوگیری از بروز خطای احتمالی در صورت عدم وجود فیلد icon در مدل Crop
        return getattr(obj.crop, 'icon', '📄') or '📄'

    crop_icon.short_description = ""

    def colored_status(self, obj):
        colors = {'draft': '#64748b', 'submitted': '#3b82f6', 'verified': '#10b981', 'rejected': '#ef4444'}
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 8px; font-size: 10px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#000'), obj.get_status_display()
        )

    colored_status.short_description = "وضعیت تایید"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            if not obj.expert:
                obj.expert = request.user
            if obj.expert and hasattr(obj.expert, 'company') and not obj.company:
                obj.company = obj.expert.company
        super().save_model(request, obj, form, change)