"""
accounts/models.py

تغییرات اصلی:
- choiceها به TextChoices تبدیل شدند (خوانایی + استفاده به‌صورت Model.Choices.X در بقیه‌ی کد).
- phone_number و national_code اعتبارسنجی regex گرفتند و national_code یکتا شد.
- فیلد تکراری rejection_reason حذف شد (manager_comment همان نقش را دارد).
- on_delete مربوط به expert در ExpertTask به PROTECT تغییر کرد تا حذف کاربر، تاریخچه‌ی
  کار را پاک نکند.
- فیلدهای reviewed_by / reviewed_at اضافه شد تا مشخص باشد چه کسی و کِی تأیید/رد کرده.
- progress_report/self_progress/verified_progress سقف ۱۰۰ گرفتند.
"""
from django.contrib.gis.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.db.models.signals import m2m_changed
from django.dispatch import receiver


phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message="شماره تماس باید با ۰۹ شروع شود و دقیقاً ۱۱ رقم باشد."
)


def validate_national_code(value):
    """اعتبارسنجی ساده‌ی کد ملی ایران (طول + رقم کنترل)."""
    if not value or len(value) != 10 or not value.isdigit():
        raise ValidationError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
    check = int(value[9])
    s = sum(int(value[i]) * (10 - i) for i in range(9))
    remainder = s % 11
    valid = (remainder < 2 and check == remainder) or (remainder >= 2 and check == 11 - remainder)
    if not valid:
        raise ValidationError("کد ملی وارد شده معتبر نیست.")


# ==========================================
# ۱. ساختار سازمانی و الگوها
# ==========================================

class Company(models.Model):
    class OrgType(models.TextChoices):
        AGRI = 'agri', 'وزارت جهاد کشاورزی'
        WATER = 'water', 'وزارت نیرو (شرکت منابع آب)'

    name = models.CharField(max_length=150, verbose_name="نام واحد/معاونت/سازمان/دفتر")
    org_type = models.CharField(max_length=10, choices=OrgType.choices, verbose_name="وزارتخانه مرجع")

    is_template = models.BooleanField(
        default=False,
        verbose_name="به عنوان الگوی ساختار (Template)",
        help_text="اگر الگو باشد، فیلد منطقه باید خالی بماند.",
    )
    at_national_level = models.BooleanField(default=False, verbose_name="فعال در سطح کشوری")
    at_province_level = models.BooleanField(default=False, verbose_name="فعال در تمام استان‌ها")
    at_city_level = models.BooleanField(default=False, verbose_name="فعال در تمام شهرستان‌ها")
    at_section_level = models.BooleanField(default=False, verbose_name="فعال در تمام بخش‌ها")

    region = models.ForeignKey(
        'Region', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name="منطقه استقرار واحد",
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_units', verbose_name="واحد بالادست",
    )
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعالیت")

    class Meta:
        verbose_name = "ساختار سازمانی"
        verbose_name_plural = "چارت سازمانی"

    def clean(self):
        super().clean()
        if self.is_template and self.region:
            raise ValidationError({'region': "یک واحد 'الگو' نمی‌تواند منطقه استقرار خاص داشته باشد."})
        if not self.is_template and not self.region:
            raise ValidationError({'region': "واحدهای اجرایی واقعی حتماً باید یک منطقه استقرار داشته باشند."})

    def save(self, *args, **kwargs):
        # توجه: full_clean در save یعنی هر save() (حتی داخل seed/bulk) کوئری و
        # اعتبارسنجی کامل انجام می‌دهد. برای import انبوه از bulk_create بدون
        # این متد یا با پرچم صریح استفاده کنید.
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        prefix = "[الگو] " if self.is_template else ""
        return f"{prefix}{self.get_org_type_display()} - {self.name}"


# ==========================================
# ۲. تقسیمات کشوری و مناطق
# ==========================================

class Region(models.Model):
    class Level(models.IntegerChoices):
        COUNTRY = 1, 'کشور (ستاد مرکزی)'
        BASIN = 2, 'حوزه آبریز / قطب کشاورزی'
        PROVINCE = 3, 'استان'
        CITY = 4, 'شهرستان'
        SECTION = 5, 'بخش'
        FARM_AREA = 6, 'محدوده بهره‌برداری (مزرعه / روستا)'

    name = models.CharField(max_length=100, verbose_name="نام منطقه")
    level = models.IntegerField(choices=Level.choices, verbose_name="سطح تقسیمات")
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_regions', verbose_name="منطقه بالادست",
    )
    geom = models.MultiPolygonField(srid=4326, verbose_name="مرز جغرافیایی", null=True, blank=True)

    def is_descendant_of(self, other_region):
        current = self.parent
        while current:
            if current == other_region:
                return True
            current = current.parent
        return False

    def get_all_subregions_ids(self):
        """
        نکته: قبلاً این منطق سه‌جای مختلف پروژه (اینجا، در
        IndicatorDefinition._get_subregion_ids و در
        accounts/views.py::_get_company_and_sub_ids) جدا نوشته شده بود. حالا
        فقط یک پیاده‌سازی مرکزی در accounts/tree_utils.py وجود دارد و همه‌جا
        همان را صدا می‌زنند.

        نکته‌ی کارایی: get_subtree_ids در tree_utils.py کل جدول Region را با
        یک کوئری واحد می‌خواند و درخت را در پایتون می‌سازد (نه یک کوئری به
        ازای هر گره)، که برای جدول‌هایی با چند هزار رکورد بسیار سریع‌تر از
        نسخه‌ی قبلی (بازگشتی + یک کوئری در هر گره) است. برای درخت‌های بسیار
        بزرگ‌تر یا پیمایش‌های پرتکرار، مهاجرت به django-treebeard/django-mptt
        یا یک CTE بازگشتی در PostgreSQL هم‌چنان گزینه‌ی بهتری است.
        """
        from .tree_utils import get_subtree_ids
        return get_subtree_ids(Region, self.id)

    class Meta:
        verbose_name = "منطقه جغرافیایی"
        verbose_name_plural = "مناطق و تقسیمات"

    def __str__(self):
        return f"{self.get_level_display()}: {self.name}"


# ==========================================
# ۳. مدیریت کاربران (Custom User)
# ==========================================

class CustomUser(AbstractUser):
    class UserType(models.TextChoices):
        OFFICIAL = 'official', 'پرسنل اداری / دولتی'
        FARMER = 'farmer', 'بهره‌بردار (کشاورز)'

    class Position(models.TextChoices):
        HEAD = 'head', 'مدیر کل / رئیس واحد'
        DEPUTY = 'deputy', 'معاون مدیر'
        GROUP_LEADER = 'group_leader', 'مدیر گروه / رئیس اداره'
        EXPERT = 'expert', 'کارشناس مسئول'
        STAFF = 'staff', 'کارشناس عملیاتی'

    class OfficeLevel(models.TextChoices):
        NATIONAL = 'national', 'ستاد مرکزی (کشوری)'
        PROVINCE = 'province', 'سطح استان'
        CITY = 'city', 'سطح شهرستان'
        SECTION = 'section', 'سطح بخش'

    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.OFFICIAL,
                                  verbose_name="نوع کاربر")
    position = models.CharField(max_length=20, choices=Position.choices, null=True, blank=True,
                                 verbose_name="سمت اداری")
    office_level = models.CharField(max_length=20, choices=OfficeLevel.choices, null=True, blank=True,
                                     verbose_name="سطح فعالیت")

    company = models.ForeignKey(Company, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='users', verbose_name="واحد خدمتی")
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='subordinates', verbose_name="ایجاد شده توسط")
    managed_region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="managers", verbose_name="منطقه تحت مدیریت (اداری)")
    chosen_region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="local_farmers", verbose_name="منطقه فعالیت کشاورز")

    phone_number = models.CharField(max_length=11, verbose_name="شماره تماس", null=True, blank=True,
                                     validators=[phone_validator])
    national_code = models.CharField(max_length=10, verbose_name="کد ملی", null=True, blank=True,
                                      unique=True, validators=[validate_national_code])
    is_approved = models.BooleanField(default=False, verbose_name="تایید صلاحیت")
    can_approve_farmers = models.BooleanField(default=False,
                                               verbose_name="دارای دسترسی تایید صلاحیت کشاورزان زیرمجموعه")

    def save(self, *args, **kwargs):
        if self.position in [self.Position.HEAD, self.Position.DEPUTY]:
            self.is_approved = True
        if self.user_type == self.UserType.FARMER:
            self.position, self.office_level, self.company = None, None, None
        super().save(*args, **kwargs)


# ==========================================
# ۴. سیستم فعالیت‌های درختی و مدیریت پیشرفت و جریان کار
# ==========================================

class Activity(models.Model):
    class OrgTypeLimit(models.TextChoices):
        AGRI = 'agri', 'کشاورزی'
        WATER = 'water', 'آب'

    title = models.CharField(max_length=250, verbose_name="عنوان فعالیت/وظیفه")
    description = models.TextField(verbose_name="شرح استاندارد", blank=True)
    org_type_limit = models.CharField(max_length=10, choices=OrgTypeLimit.choices, verbose_name="حوزه مربوطه")

    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_activities', verbose_name="فعالیت بالادست",
    )

    weight = models.PositiveIntegerField(default=1, verbose_name="وزن (اهمیت)")
    self_progress = models.PositiveIntegerField(
        default=0, verbose_name="پیشرفت اعلامی کارشناس", validators=[MaxValueValidator(100)]
    )
    verified_progress = models.PositiveIntegerField(
        default=0, verbose_name="پیشرفت تایید شده نهایی", validators=[MaxValueValidator(100)]
    )

    assigned_companies = models.ManyToManyField('Company', related_name='activities', verbose_name="سازمان‌های متولی")

    class Meta:
        verbose_name = "فعالیت و وظیفه"
        verbose_name_plural = "ساختار فعالیت‌ها و وظایف"

    def __str__(self):
        return f"{self.title} ({'زیرمجموعه: ' + self.parent.title if self.parent else 'پروژه اصلی'})"

    def calculate_total_progress(self):
        """
        نکته‌ی کارایی: بازگشتی است و برای هر زیرفعالیت کوئری جدا می‌زند. برای
        درخت‌های عمیق با prefetch_related('sub_activities') یا کتابخانه‌ی درختی
        بهینه‌سازی کنید.
        """
        sub_activities = self.sub_activities.all()
        if not sub_activities:
            return self.verified_progress
        total_weight = sum(sub.weight for sub in sub_activities)
        if total_weight == 0:
            return 0
        weighted_sum = sum(sub.calculate_total_progress() * sub.weight for sub in sub_activities)
        return weighted_sum / total_weight

    def save(self, *args, **kwargs):
        if self.weight == 0:
            self.weight = 1
        super().save(*args, **kwargs)


class ExpertTask(models.Model):
    class Status(models.TextChoices):
        PENDING_ASSIGNMENT = 'pending_assignment', 'در انتظار ارجاع و تقسیم وظایف'
        PENDING = 'pending', 'در انتظار پاسخ و ثبت متغیرها'
        SUBMITTED = 'submitted', 'ارسال شده برای بررسی بالادست'
        APPROVED = 'approved', 'تایید شده نهایی'
        REJECTED = 'rejected', 'رد شده / نیازمند اصلاح زیرمجموعه'

    # توجه: on_delete برای expert از CASCADE به PROTECT تغییر کرد تا حذف یک
    # کاربر، تاریخچه‌ی وظایف/تأییدها را پاک نکند. اگر واقعاً باید کاربر حذف
    # شدنی باشد، اول باید کاربران را غیرفعال (is_active=False) کنید نه حذف.
    expert = models.ForeignKey('CustomUser', on_delete=models.PROTECT, related_name='assigned_tasks',
                                verbose_name="مسئول فعلی")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, verbose_name="فعالیت/وظیفه محوله")
    crop = models.ForeignKey('indicators.Crop', on_delete=models.SET_NULL, null=True, blank=True,
                              verbose_name="محصول مرتبط")
    target_regions = models.ManyToManyField('Region', related_name='assigned_tasks', verbose_name="مناطق تحت پوشش")

    assigned_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='created_tasks', verbose_name="ارجاع‌دهنده وظیفه")
    parent_task = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='sub_tasks', verbose_name="وظیفه مبدا بالادست")

    progress_report = models.PositiveIntegerField(
        default=0, verbose_name="درصد پیشرفت گزارش شده", validators=[MaxValueValidator(100)]
    )
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDING_ASSIGNMENT,
                               verbose_name="وضعیت تایید")

    # فیلد rejection_reason حذف شد؛ manager_comment همین نقش را ایفا می‌کرد و
    # داشتن هر دو باعث سردرگمی می‌شد (کدام باید پر شود؟). اگر داده‌ی تاریخی در
    # rejection_reason دارید، قبل از حذف یک migration داده بنویسید که آن را به
    # manager_comment منتقل کند.
    manager_comment = models.TextField(blank=True, verbose_name="توضیحات و دلایل رد کار")

    is_active = models.BooleanField(default=True, verbose_name="وضعیت ابلاغیه")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد ارجاع")

    # اضافه شد: مشخص می‌کند چه کسی و کِی تأیید/رد کرده (قبلاً هیچ‌جا ثبت نمی‌شد)
    reviewed_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reviewed_tasks', verbose_name="بررسی‌کننده")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان بررسی")

    class Meta:
        verbose_name = "ابلاغ وظیفه"
        verbose_name_plural = "ابلاغ وظایف و نظارت"

    def __str__(self):
        return f"{self.expert.get_full_name() or self.expert.username} -> {self.activity.title}"


# ==========================================
# ۵. سیگنال‌ها و پروکسی مدل‌ها
# ==========================================

@receiver(m2m_changed, sender=ExpertTask.target_regions.through)
def validate_task_regions_integrity(sender, instance, action, pk_set, **kwargs):
    if action == "pre_add":
        expert_managed_region = instance.expert.managed_region
        if not expert_managed_region:
            raise ValidationError("ابتدا باید برای کارشناس منطقه مدیریت تعیین کنید.")
        allowed_ids = set(expert_managed_region.get_all_subregions_ids())
        invalid_ids = set(pk_set) - allowed_ids
        if invalid_ids:
            names = Region.objects.filter(id__in=invalid_ids).values_list('name', flat=True)
            raise ValidationError(f"مناطق ({', '.join(names)}) خارج از قلمرو مدیریتی است.")


class OfficialUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "پرسنل اداری"
        verbose_name_plural = "مدیریت پرسنل اداری"


class FarmerUser(CustomUser):
    class Meta:
        proxy = True
        verbose_name = "بهره‌بردار (کشاورز)"
        verbose_name_plural = "مدیریت کشاورزان"
