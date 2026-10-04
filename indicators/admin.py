from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import Region

from .models import (
    CropCategory, CropFamily, Crop, CropVariety, IndicatorDefinition,
    VariableDefinition, ExpertAnswerSubmission, ExpertAnswerDetail,
    RegionIndicatorComment,
)


# ۰. مدیریت دسته‌بندی‌های کلان
@admin.register(CropCategory)
class CropCategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'icon', 'crop_count')

    def crop_count(self, obj):
        return obj.crops.count()

    crop_count.short_description = "تعداد محصولات"


# ۰.۱. مدیریت خانواده‌های گیاهی
@admin.register(CropFamily)
class CropFamilyAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'crop_count')

    def crop_count(self, obj):
        return obj.crops.count()

    crop_count.short_description = "تعداد محصولات این خانواده"


# ۰.۲. مدیریت واریته‌های محصول
@admin.register(CropVariety)
class CropVarietyAdmin(admin.ModelAdmin):
    search_fields = ('name', 'crop__name')
    list_display = ('name', 'crop', 'description')
    list_filter = ('crop',)


# ۱. اینلاین‌ها برای صفحه محصول
class VariableDefinitionInline(admin.TabularInline):
    model = VariableDefinition
    extra = 1
    # فیلد field_type حذف شد (همه‌ی متغیرها همیشه عددی‌اند؛ نگاه کنید به
    # توضیح بالای models.py).
    fields = ('code', 'name', 'activity', 'target_indicator', 'order', 'is_obsolete')
    readonly_fields = ('code',)
    ordering = ('order',)


class CropVarietyInline(admin.TabularInline):
    model = CropVariety
    extra = 2
    fields = ('name', 'description')


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    search_fields = ('name', 'slug', 'category__name', 'family__name')
    list_display = ('name', 'slug', 'category', 'family', 'is_active', 'variable_count')
    list_editable = ('category', 'family', 'is_active')
    list_filter = ('category', 'family', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [VariableDefinitionInline, CropVarietyInline]

    def variable_count(self, obj):
        return obj.variables.count()

    variable_count.short_description = "تعداد سوالات"


class IndicatorDefinitionAdminForm(forms.ModelForm):
    """
    IndicatorDefinition.calculation_levels یک JSONField (لیستی از اعداد
    سطح) است. این فرم آن را به یک چک‌باکس چندانتخابی در پنل ادمین تبدیل
    می‌کند (ادمین باید بتواند مثلاً هم‌زمان «کشوری» و «استانی» را تیک بزند)
    و در save() به/از لیست JSON تبدیل می‌کند.
    """
    calculation_levels = forms.MultipleChoiceField(
        choices=Region.Level.choices,
        widget=forms.CheckboxSelectMultiple,
        label="سطوح محاسبه",
        help_text="این شاخص در کدام سطح/سطوح جغرافیایی قابل محاسبه و نمایش باشد؟",
    )

    class Meta:
        model = IndicatorDefinition
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['calculation_levels'] = [str(lvl) for lvl in (self.instance.calculation_levels or [])]

    def clean_calculation_levels(self):
        return [int(v) for v in self.cleaned_data['calculation_levels']]


@admin.register(IndicatorDefinition)
class IndicatorDefinitionAdmin(admin.ModelAdmin):
    form = IndicatorDefinitionAdminForm
    list_display = ('name', 'scope', 'scope_target_display', 'levels_display', 'unit',
                     'breakdown_summary', 'visible_to_farmers', 'formula_display')
    list_filter = ('scope', 'target_category', 'target_family', 'visible_to_farmers')
    search_fields = ('name', 'formula')

    fieldsets = (
        ("تعریف پایه شاخص", {
            'fields': ('name', 'unit', 'formula'),
            'description': mark_safe(
                '<div style="background: #eff6ff; padding: 10px; border-right: 4px solid #3b82f6; color: #1e40af; font-size: 0.85rem;">'
                '<strong>راهنمای فرمول‌نویسی پیشرفته:</strong><br>'
                '• برای نرمال‌سازی: <code>yield / yield_max</code><br>'
                '• فرمول شرطی: <code>(yield * 1.1) if yield > 5 else (yield * 0.9)</code><br>'
                '• توابع ریاضی: <code>sqrt(yield)</code> یا <code>yield ** 2</code><br>'
                '• عملگرهای مجاز: <code>+ - * / **</code> و پرانتز <code>()</code>'
                '</div>'
            )
        }),
        ("دامنه شمول (محصولی)", {
            'fields': ('scope', 'target_category', 'target_family'),
            'description': "اگر دامنه 'دسته محصولات' است، دسته هدف را انتخاب کنید؛ اگر 'خانواده گیاهی' است، خانواده هدف را.",
        }),
        ("ریزکاوی اختیاری (Drill-down محصولی)", {
            'fields': ('breakdown_by_family', 'breakdown_by_crop', 'breakdown_by_variety'),
            'description': "علاوه بر عدد کلی دسته/خانواده، همان شاخص به تفکیک خانواده/محصول/رقم هم محاسبه و قابل مشاهده باشد.",
        }),
        ("سطح جغرافیایی و دسترسی", {
            'fields': ('calculation_levels', 'visible_to_farmers'),
        }),
    )

    def scope_target_display(self, obj):
        if obj.scope == 'category':
            return obj.target_category or '—'
        if obj.scope == 'family':
            return obj.target_family or '—'
        return obj.get_scope_display()

    scope_target_display.short_description = "هدف دامنه"

    def levels_display(self, obj):
        level_map = dict(Region.Level.choices)
        return '، '.join(level_map.get(lvl, str(lvl)) for lvl in (obj.calculation_levels or []))

    levels_display.short_description = "سطوح محاسبه"

    def breakdown_summary(self, obj):
        parts = []
        if obj.breakdown_by_family:
            parts.append('خانواده')
        if obj.breakdown_by_crop:
            parts.append('محصول')
        if obj.breakdown_by_variety:
            parts.append('رقم')
        return '، '.join(parts) if parts else '—'

    breakdown_summary.short_description = "ریزکاوی"

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
        # نکته: obj اینجا شیء والد (ExpertAnswerSubmission) است، نه خودِ
        # ردیف اینلاین؛ پس obj.status واقعاً معتبر است (و باگ نیست).
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


@admin.register(RegionIndicatorComment)
class RegionIndicatorCommentAdmin(admin.ModelAdmin):
    """عمدتاً برای نظارت/دیباگ؛ گفتگوی روزمره از پنل نقشه‌ی شاخص‌ها (manager_summary.html) انجام می‌شود."""
    list_display = ('region', 'author', 'indicator', 'crop', 'short_message', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'region__level')
    search_fields = ('region__name', 'author__username', 'message')
    autocomplete_fields = ['region', 'author', 'indicator', 'crop', 'parent']

    def short_message(self, obj):
        return obj.message[:50]

    short_message.short_description = "متن"
