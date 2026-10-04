from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis import admin as gis_admin
from django.utils.html import format_html
from django.db.models import Q
from django.contrib import messages
from .models import (
    CustomUser, Region, Company, OfficialUser, FarmerUser,
    Activity, ExpertTask
)


# ۱. مدل پایه (مخفی برای Autocomplete و رفع خطاهای ارجاع)
@admin.register(CustomUser)
class CustomUserBaseAdmin(UserAdmin):
    search_fields = ['username', 'first_name', 'last_name', 'national_code']
    list_display = ['username', 'user_type', 'is_active']

    def get_model_perms(self, request):
        # مخفی کردن از منوی اصلی ادمین، فقط برای autocomplete استفاده می‌شود
        return {}


# ۲. اینلاین زیر‌فعالیت‌ها برای نمایش درختی در صفحه فعالیت مادر
class SubActivityInline(admin.TabularInline):
    model = Activity
    fk_name = 'parent'
    extra = 1
    fields = ['title', 'weight', 'verified_progress', 'org_type_limit']
    verbose_name = "زیر‌فعالیت / وظیفه"
    verbose_name_plural = "لیست زیر‌فعالیت‌های این مجموعه"


from django.contrib.gis import admin as gis_admin



# ۳. مدیریت مناطق جغرافیایی (با تنظیمات صحیح سیستم مختصات در نسخه جدید جنگو)
@admin.register(Region)
class RegionAdmin(gis_admin.GISModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'level', 'parent']
    list_filter = ['level']
    autocomplete_fields = ['parent']

    # تنظیمات ویجت نقشه و ابعاد آن
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 5,
            'default_lon': 53.6880,
            'default_lat': 32.4279,
            'map_width': 800,
            'map_height': 500,
        }
    }

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('parent')


# ۴. مدیریت ساختار سازمانی
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'org_type', 'is_template', 'region', 'is_active']
    list_filter = ['is_template', 'org_type', 'is_active']
    autocomplete_fields = ['parent', 'region']
    fieldsets = (
        ("مشخصات واحد", {'fields': ('name', 'org_type', 'parent', 'is_active')}),
        ("نوع واحد", {'fields': ('is_template', 'region')}),
        ("تنظیمات الگو (Template)", {
            'fields': ('at_national_level', 'at_province_level', 'at_city_level', 'at_section_level'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('parent', 'region')
# ۵. مدیریت پرسنل اداری
@admin.register(OfficialUser)
class OfficialUserAdmin(UserAdmin):
    search_fields = ['username', 'first_name', 'last_name', 'national_code', 'phone_number']
    list_display = ['username', 'get_full_name', 'colored_position', 'company', 'managed_region', 'is_approved']
    list_filter = ['position', 'office_level', 'is_approved', 'company']
    autocomplete_fields = ['company', 'managed_region', 'created_by']

    fieldsets = (
        ("🔐 دسترسی سیستمی",
         {'fields': ('username', 'password', 'is_active', 'is_staff', 'is_superuser', 'is_approved', 'created_by',
                     'can_approve_farmers')}),
        ("👤 اطلاعات فردی", {'fields': ('first_name', 'last_name', 'national_code', 'phone_number')}),
        ("🏢 چارت سازمانی", {'fields': ('company', 'position', 'office_level')}),
        ("📍 قلمرو مدیریت", {'fields': ('managed_region',)}),
    )

    add_fieldsets = (
        ("ایجاد کاربر اداری جدید", {
            'classes': ('wide',),
            'fields': ('username', 'password', 'first_name', 'last_name', 'national_code', 'phone_number',
                       'company', 'position', 'office_level', 'managed_region', 'is_approved'),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(user_type='official').select_related('company', 'managed_region')
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'managed_region') and request.user.managed_region:
            return qs.filter(Q(created_by=request.user) | Q(managed_region__parent=request.user.managed_region))
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        obj.user_type = 'official'
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user

        if not change or 'password' in form.changed_data:
            if obj.password and not obj.password.startswith(('pbkdf2_sha256\(', 'argon2\)', 'bcrypt$')):
                obj.set_password(obj.password)

        super().save_model(request, obj, form, change)

    def colored_position(self, obj):
        colors = {
            'head': '#1e3a8a',
            'deputy': '#1e40af',
            'group_leader': '#059669',
            'expert': '#d97706',
            'staff': '#7c3aed'
        }
        position_name = obj.get_position_display() if hasattr(obj, 'get_position_display') else obj.position
        return format_html('**{}**', colors.get(obj.position, '#000'), position_name or '-')

    colored_position.short_description = "سمت اداری"


# ۶. مدیریت کشاورزان (ایزوله شده)
@admin.register(FarmerUser)
class FarmerUserAdmin(UserAdmin):
    search_fields = ['username', 'first_name', 'last_name', 'phone_number', 'national_code']
    list_display = ['username', 'get_full_name', 'phone_number', 'chosen_region', 'is_approved']
    list_filter = ['is_approved', 'chosen_region']
    autocomplete_fields = ['chosen_region']

    fieldsets = (
        ("🔐 حساب کاربری کشاورز", {'fields': ('username', 'password', 'is_active', 'is_approved')}),
        ("👤 مشخصات بهره‌‌بردار", {'fields': ('first_name', 'last_name', 'national_code', 'phone_number')}),
        ("📍 محل فعالیت", {'fields': ('chosen_region',)}),
    )

    add_fieldsets = (
        ("ایجاد کشاورز جدید", {
            'classes': ('wide',),
            'fields': ('username', 'password', 'first_name', 'last_name', 'national_code', 'phone_number',
                       'chosen_region', 'is_approved'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user_type='farmer').select_related('chosen_region')

    def save_model(self, request, obj, form, change):
        obj.user_type = 'farmer'
        obj.is_staff = False

        if not change or 'password' in form.changed_data:
            if obj.password and not obj.password.startswith(('pbkdf2_sha256\(', 'argon2\)', 'bcrypt$')):
                obj.set_password(obj.password)

        super().save_model(request, obj, form, change)


# ۷. مدیریت فعالیت‌ها (درختی و محاسباتی)
@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    search_fields = ['title']
    list_display = ['title', 'parent', 'weight', 'get_total_progress_display', 'org_type_limit']
    list_filter = ['org_type_limit']
    autocomplete_fields = ['parent', 'assigned_companies']
    inlines = [SubActivityInline]

    fieldsets = (
        ("اطلاعات اصلی", {'fields': ('title', 'parent', 'description', 'org_type_limit')}),
        ("وزن و سازمان‌ها", {'fields': ('weight', 'assigned_companies')}),
        ("وضعیت پیشرفت", {'fields': ('self_progress', 'verified_progress')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('parent').prefetch_related('assigned_companies')

    @admin.display(description="پیشرفت کل پروژه")
    def get_total_progress_display(self, obj):
        progress = obj.calculate_total_progress() if hasattr(obj, 'calculate_total_progress') else 0
        color = "red" if progress < 30 else "orange" if progress < 70 else "green"
        return format_html('**{}%**', color, round(progress, 2))


# ۸. ابلاغ وظایف و چرخه تایید سلسله‌مراتبی
@admin.register(ExpertTask)
class ExpertTaskAdmin(admin.ModelAdmin):
    search_fields = ['expert__username', 'expert__last_name', 'activity__title']
    list_display = ['expert', 'activity', 'colored_status', 'progress_report', 'assigned_by', 'is_active']
    list_filter = ['status', 'is_active', 'activity']
    autocomplete_fields = ['expert', 'activity', 'target_regions', 'assigned_by', 'parent_task']
    actions = ['approve_tasks_action']

    fieldsets = (
        ("مسئولیت و محتوا", {'fields': ('expert', 'activity', 'target_regions', 'is_active')}),
        ("سلسله‌مراتب ارجاع (موتور جریان کار)", {'fields': ('assigned_by', 'parent_task')}),
        ("گزارش عملکرد و بازبینی", {'fields': ('status', 'progress_report', 'manager_comment', 'rejection_reason')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('expert', 'activity', 'assigned_by',
                                                            'parent_task').prefetch_related('target_regions')

    @admin.action(description='تایید نهایی گزارش‌ها (تایید مستقیم از ادمین) و اعمال بر روی شاخص‌ها')
    def approve_tasks_action(self, request, queryset):
        count = 0
        for task in queryset:
            task.status = 'approved'
            task.save()

            if task.activity:
                act = task.activity
                act.verified_progress = task.progress_report
                act.save()

            # تایید فرم‌های ثبت‌شده مربوط به همین کارشناس و مناطق این تسک
            try:
                from indicators.models import ExpertAnswerSubmission
                regions = task.target_regions.all()
                if regions:
                    ExpertAnswerSubmission.objects.filter(
                        expert=task.expert,
                        region__in=regions
                    ).update(status='verified')
                else:
                    ExpertAnswerSubmission.objects.filter(
                        expert=task.expert
                    ).update(status='verified')
            except ImportError:
                pass
            count += 1

        self.message_user(request, f"تعداد {count} وظیفه با موفقیت تایید نهایی شدند و پیشرفت آنها اعمال گردید.",
                          messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.assigned_by:
            obj.assigned_by = request.user

        if not obj.pk and obj.status == 'pending_assignment' and getattr(obj.expert, 'position', None) == 'staff':
            obj.status = 'pending'

        super().save_model(request, obj, form, change)

        # ساخت خودکار Submission پس از ذخیره تسک در صورت وجود اپلیکیشن indicators
        if obj.activity:
            try:
                from indicators.models import ExpertAnswerSubmission, VariableDefinition, ExpertAnswerDetail

                regions = list(obj.target_regions.all())
                if not regions and getattr(obj.expert, 'managed_region', None):
                    regions = [obj.expert.managed_region]

                for region in regions:
                    submission, _ = ExpertAnswerSubmission.objects.get_or_create(
                        expert=obj.expert,
                        region=region,
                        defaults={
                            'status': 'draft',
                            'company': getattr(obj.expert, 'company', None)
                        }
                    )

                    related_vars = VariableDefinition.objects.filter(activity=obj.activity)
                    for var in related_vars:
                        ExpertAnswerDetail.objects.get_or_create(
                            submission=submission,
                            variable=var,
                            defaults={'value': 0}
                        )
            except (ImportError, Exception):
                pass

    def colored_status(self, obj):
        colors = {
            'pending_assignment': '#7c3aed',
            'pending': '#d97706',
            'submitted': '#2563eb',
            'approved': '#16a34a',
            'rejected': '#dc2626',
        }
        return format_html('**{}**', colors.get(obj.status, '#000'), obj.get_status_display())

    colored_status.short_description = "وضعیت تایید"