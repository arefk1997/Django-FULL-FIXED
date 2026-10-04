"""
indicators/models.py

تغییرات این نسخه نسبت به نسخه‌ی قبلی (خلاصه؛ توضیح کامل هر بخش در کنار
همان کد آمده است):

1) IndicatorDefinition اکنون می‌تواند هم‌زمان روی چند سطح جغرافیایی
   (calculation_levels) معنی داشته باشد (مثلاً هم کشوری هم استانی)،
   به‌جای یک سطح ثابت.
2) یک شاخص تعریف‌شده برای یک دسته/خانواده می‌تواند اختیاری «ریزتر» هم
   محاسبه شود (breakdown_by_family / breakdown_by_crop / breakdown_by_variety)
   تا در داشبورد بتوان مثل drill-down هم خود دسته و هم اجزای داخلش را دید.
3) target_family اضافه شد تا scope='family' واقعاً قابل انتخاب باشد (قبلاً
   این گزینه در SCOPE_CHOICES بود ولی هیچ فیلدی برای انتخاب «کدام خانواده»
   وجود نداشت و در calculate_smart هم پیاده نشده بود).
4) visible_to_farmers اضافه شد: به‌صورت پیش‌فرض هیچ شاخصی برای کشاورزان
   نمایش داده نمی‌شود، مگر این‌که ادمین صریحاً همین پرچم را فعال کند.
5) مدل جدید RegionIndicatorComment: تردهای کامنت سلسله‌مراتبی روی یک
   منطقه (و اختیاراً یک شاخص/محصول مشخص)، برای گفتگوی مدیر بالادست با
   مسئول همان منطقه.
6) VariableDefinition.field_type حذف شد. این فیلد ناسازگار بود: مقدار
   'text' قابل انتخاب بود ولی ExpertAnswerDetail.value یک DecimalField
   خالص است (نمی‌تواند متن نگه دارد) و در views.py هم فقط فرم عددی واقعاً
   کار می‌کرد. چون این متغیرها صرفاً برای فرمول‌نویسی عددی استفاده می‌شوند،
   همه‌شان همیشه عددی هستند؛ نیازی به این فیلد نیست.
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Max, Min, Sum

from accounts.models import Activity, Company, Region

from .safe_eval import UnsafeExpressionError, safe_eval_formula


class CropCategory(models.Model):
    """۱. دسته‌بندی کلان (غلات، صیفی‌جات و ...)"""
    name = models.CharField(max_length=100, unique=True, verbose_name="نام دسته")
    icon = models.CharField(max_length=50, blank=True, verbose_name="آیکون دسته")

    class Meta:
        verbose_name = "دسته محصول"
        verbose_name_plural = "۰. دسته‌بندی محصولات"

    def __str__(self):
        return self.name


class CropFamily(models.Model):
    """۲. خانواده گیاهی (گندمیان، باقلاسانان و ...)"""
    name = models.CharField(max_length=100, unique=True, verbose_name="نام خانواده گیاهی")
    description = models.TextField(blank=True, verbose_name="توضیحات علمی")

    class Meta:
        verbose_name = "خانواده گیاهی"
        verbose_name_plural = "۰.۱. خانواده‌های گیاهی"

    def __str__(self):
        return self.name


class Crop(models.Model):
    """۳. محصول با شناسه انگلیسی (Slug)"""
    category = models.ForeignKey(CropCategory, on_delete=models.PROTECT, related_name='crops', verbose_name="دسته")
    family = models.ForeignKey(CropFamily, on_delete=models.SET_NULL, null=True, blank=True, related_name='crops',
                                verbose_name="خانواده")
    name = models.CharField(max_length=100, unique=True, verbose_name="نام محصول (فارسی)")
    slug = models.SlugField(max_length=50, unique=True, verbose_name="شناسه انگلیسی", null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعالیت")
    icon = models.CharField(max_length=50, blank=True, verbose_name="آیکون/اموجی")

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "۱. محصولات"

    def __str__(self):
        return f"{self.name} ({self.slug})"


class CropVariety(models.Model):
    """۴. رقم محصول"""
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='varieties', verbose_name="محصول")
    name = models.CharField(max_length=100, verbose_name="نام رقم")
    description = models.TextField(blank=True, verbose_name="ویژگی‌های رقم")

    class Meta:
        verbose_name = "رقم محصول"
        verbose_name_plural = "۱.۱. ارقام محصولات"
        unique_together = ('crop', 'name')

    def __str__(self):
        return f"{self.crop.name} (رقم {self.name})"


def _default_calculation_levels():
    """پیش‌فرض: فقط سطح بخش/مزرعه (همان رفتار نسخه‌ی قبلی با calculation_level=5)."""
    return [5]


class IndicatorDefinition(models.Model):
    """۵. تعریف شاخص‌ها با پشتیبانی از فرمول‌های شرطی، چند سطح جغرافیایی و ریزکاوی (drill-down)."""

    # همان سطوح Region.LEVEL_CHOICES (کشور تا محدوده بهره‌برداری) تا هیچ
    # ناسازگاری بین سطح یک شاخص و سطح واقعی مناطق پیش نیاید.
    LEVEL_CHOICES = Region.Level.choices

    SCOPE_CHOICES = (
        ('single', 'تک محصولی'), ('category', 'گروه محصولات (دسته)'),
        ('family', 'خانواده گیاهی'), ('all', 'عمومی (تمام محصولات)'),
    )

    name = models.CharField(max_length=200, verbose_name="نام شاخص")

    # قبلاً calculation_level یک IntegerField تکی بود (یک شاخص فقط در یک
    # سطح جغرافیایی - مثلاً فقط استانی - قابل محاسبه بود). حالا یک شاخص
    # می‌تواند هم‌زمان در چند سطح (مثلاً هم کشوری هم استانی هم شهرستانی)
    # محاسبه و در داشبورد drill-down نمایش داده شود.
    calculation_levels = models.JSONField(
        default=_default_calculation_levels,
        verbose_name="سطوح محاسبه",
        help_text="این شاخص در کدام سطح/سطوح جغرافیایی معنی دارد و باید محاسبه شود؟",
    )

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='single', verbose_name="دامنه شمول")
    target_category = models.ForeignKey(CropCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                         verbose_name="دسته هدف (برای scope='category')")
    # اضافه شد: قبلاً scope='family' در SCOPE_CHOICES وجود داشت ولی هیچ
    # فیلدی برای انتخاب «کدام خانواده» نبود و calculate_smart هم آن را
    # پیاده نمی‌کرد؛ یعنی در عمل مثل 'all' رفتار می‌کرد.
    target_family = models.ForeignKey(CropFamily, on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name="خانواده هدف (برای scope='family')")

    # ریزکاوی اختیاری: وقتی شاخص برای یک دسته/خانواده تعریف شده، ادمین
    # می‌تواند انتخاب کند که علاوه بر عدد کلی دسته/خانواده، همان شاخص به
    # تفکیک خانواده/محصول/رقم هم محاسبه و قابل drill-down باشد.
    breakdown_by_family = models.BooleanField(
        default=False, verbose_name="تفکیک بر اساس خانواده گیاهی",
        help_text="فقط برای scope='category' یا 'all' معنی دارد.",
    )
    breakdown_by_crop = models.BooleanField(
        default=False, verbose_name="تفکیک بر اساس محصول",
        help_text="فقط برای scope='category' یا 'family' یا 'all' معنی دارد.",
    )
    breakdown_by_variety = models.BooleanField(
        default=False, verbose_name="تفکیک بر اساس رقم محصول",
        help_text="برای هر scope ای که در نهایت به یک محصول مشخص برسد معنی دارد.",
    )

    formula = models.CharField(max_length=500, null=True, blank=True, verbose_name="فرمول (کد عمومی)")
    unit = models.CharField(max_length=50, blank=True, verbose_name="واحد اندازه‌گیری")

    # اضافه شد: پیش‌فرض هیچ شاخصی برای کشاورزان نمایش داده نمی‌شود. فقط
    # شاخص‌هایی که ادمین صراحتاً این پرچم را فعال کند، در داشبورد کشاورز
    # دیده می‌شوند (نیازمندی: «کشاورز به شاخص‌ها دسترسی نداشته باشد مگر
    # شاخصی توسط ادمین برای کشاورزان تعریف شود»).
    visible_to_farmers = models.BooleanField(default=False, verbose_name="نمایش به کشاورزان")

    class Meta:
        verbose_name = "تعریف شاخص"
        verbose_name_plural = "۲. تعریف شاخص‌ها"

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # اعتبارسنجی
    # ------------------------------------------------------------------
    def clean(self):
        """اعتبارسنجی فرمول (وجود متغیرها + ساختار امن) و سطوح محاسبه."""
        valid_levels = {lvl for lvl, _ in self.LEVEL_CHOICES}
        levels = self.calculation_levels or []
        if not levels:
            raise ValidationError({'calculation_levels': "حداقل یک سطح محاسبه باید انتخاب شود."})
        if not set(levels).issubset(valid_levels):
            raise ValidationError({'calculation_levels': "یک یا چند سطح انتخاب‌شده معتبر نیستند."})

        if self.scope == 'category' and not self.target_category:
            raise ValidationError({'target_category': "برای دامنه‌ی 'دسته محصولات'، انتخاب دسته هدف الزامی است."})
        if self.scope == 'family' and not self.target_family:
            raise ValidationError({'target_family': "برای دامنه‌ی 'خانواده گیاهی'، انتخاب خانواده هدف الزامی است."})

        if not self.formula:
            return

        raw_codes = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', self.formula)
        keywords = ['if', 'else', 'and', 'or', 'not', 'min', 'max', 'round', 'abs',
                    'sqrt', 'floor', 'ceil', 'True', 'False']

        unknown_vars = []
        for code in raw_codes:
            if code in keywords or code.endswith(('_max', '_min', '_sum', '_avg')):
                continue
            exists = VariableDefinition.objects.filter(
                models.Q(code=code) | models.Q(code__startswith=f"{code}_")
            ).exists()
            if not exists:
                unknown_vars.append(code)

        if unknown_vars:
            raise ValidationError({
                'formula': f"خطا: متغیرهای ({', '.join(unknown_vars)}) در بخش 'متغیرهای ورودی' تعریف نشده‌اند."
            })

        # اعتبارسنجی ساختاری: مطمئن شویم فرمول با evaluator امن قابل پارس است
        # (بدون محاسبه‌ی واقعی مقدار - فقط با context فرضی صفر برای همه‌ی متغیرها)
        try:
            dummy_context = {code: 0 for code in raw_codes if code not in keywords}
            safe_eval_formula(self.formula, dummy_context)
        except ZeroDivisionError:
            pass  # با context صفر طبیعی است که تقسیم بر صفر رخ دهد؛ فقط ساختار مهم است
        except UnsafeExpressionError as e:
            raise ValidationError({'formula': f"فرمول شامل ساختار غیرمجاز است: {e}"})
        except SyntaxError:
            raise ValidationError({'formula': "فرمول از نظر نحوی نامعتبر است."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # محاسبه
    # ------------------------------------------------------------------
    def is_available_for_level(self, level):
        return level in (self.calculation_levels or [])

    def _get_subregion_ids(self, reg_obj):
        from accounts.tree_utils import get_subtree_ids
        return get_subtree_ids(Region, reg_obj.id)

    def calculate_smart(self, region=None, crop=None, family=None, variety=None):
        """
        محاسبه‌ی مقدار شاخص برای یک منطقه‌ی مشخص، با فیلتر اختیاری محصول/
        خانواده/رقم (برای حالت‌های ریزکاوی/drill-down).

        - region: اگر داده شود، فقط داده‌های همان منطقه و زیرشاخه‌هایش
          لحاظ می‌شود.
        - crop/family/variety: محدودکردن محاسبه به یک محصول/خانواده/رقم
          مشخص؛ وقتی هیچ‌کدام داده نشود، طبق scope خودِ شاخص عمل می‌شود
          (target_category / target_family یا کل داده‌ها).
        """
        if not self.formula:
            return None, "بدون فرمول"

        raw_codes = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', self.formula)
        context = {}
        missing_vars = []
        keywords = ['if', 'else', 'and', 'or', 'not', 'min', 'max', 'round', 'abs',
                    'sqrt', 'floor', 'ceil', 'True', 'False']

        if region:
            # همیشه زیردرخت منطقه را در نظر می‌گیریم (یک شاخص استانی باید
            # داده‌ی همه‌ی شهرستان‌ها/بخش‌های زیرمجموعه‌اش را جمع بزند).
            target_region_ids = self._get_subregion_ids(region)
        else:
            target_region_ids = []

        for raw_code in raw_codes:
            if raw_code in keywords:
                continue

            if crop:
                db_code = f"{raw_code}_{crop.slug}"
            else:
                db_code = raw_code

            queryset = ExpertAnswerDetail.objects.filter(
                variable__code=db_code,
                submission__status='verified',
            )

            if target_region_ids:
                queryset = queryset.filter(submission__region_id__in=target_region_ids)

            if variety:
                queryset = queryset.filter(submission__variety=variety)
            elif crop:
                queryset = queryset.filter(submission__crop=crop)
            elif family:
                queryset = queryset.filter(submission__crop__family=family)
            elif self.scope == 'family' and self.target_family:
                queryset = queryset.filter(submission__crop__family=self.target_family)
            elif self.scope == 'category' and self.target_category:
                queryset = queryset.filter(submission__crop__category=self.target_category)

            stats = queryset.aggregate(
                val_avg=Avg('value'), val_max=Max('value'),
                val_min=Min('value'), val_sum=Sum('value'),
            )

            if stats['val_avg'] is not None:
                context[raw_code] = float(stats['val_avg'])
                context[f"{raw_code}_max"] = float(stats['val_max'])
                context[f"{raw_code}_min"] = float(stats['val_min'])
                context[f"{raw_code}_sum"] = float(stats['val_sum'])
            else:
                if raw_code not in context:
                    missing_vars.append(raw_code)

        missing_vars = [v for v in set(missing_vars) if v not in context]
        if missing_vars:
            return None, f"نقص داده در: {', '.join(missing_vars)}"

        try:
            result = safe_eval_formula(self.formula, context)
            return round(result, 3), "تکمیل شده"
        except ZeroDivisionError:
            return None, "خطا در فرمول: تقسیم بر صفر"
        except (UnsafeExpressionError, SyntaxError) as e:
            return None, f"خطا در فرمول: {e}"

    def calculate_breakdown(self, region=None):
        """
        بسته به پرچم‌های breakdown_by_*، علاوه بر عدد کلی، لیستی از مقادیر
        تفکیک‌شده (برای drill-down داخل همان منطقه، نه جغرافیایی) برمی‌گرداند.
        خروجی: [{'label': ..., 'value': ..., 'status': ...}, ...]
        """
        rows = []
        overall_value, overall_status = self.calculate_smart(region=region)
        rows.append({'label': 'کل', 'value': overall_value, 'status': overall_status})

        if self.breakdown_by_family:
            families = CropFamily.objects.filter(crops__category=self.target_category).distinct() \
                if self.scope == 'category' and self.target_category else CropFamily.objects.all()
            for fam in families:
                value, status = self.calculate_smart(region=region, family=fam)
                if value is not None:
                    rows.append({'label': f"خانواده: {fam.name}", 'value': value, 'status': status})

        if self.breakdown_by_crop:
            crops_qs = Crop.objects.filter(is_active=True)
            if self.scope == 'category' and self.target_category:
                crops_qs = crops_qs.filter(category=self.target_category)
            elif self.scope == 'family' and self.target_family:
                crops_qs = crops_qs.filter(family=self.target_family)
            for crop in crops_qs:
                value, status = self.calculate_smart(region=region, crop=crop)
                if value is not None:
                    rows.append({'label': f"محصول: {crop.name}", 'value': value, 'status': status})

        if self.breakdown_by_variety:
            variety_qs = CropVariety.objects.all()
            if self.scope == 'single':
                pass  # رقم بدون محصول مشخص معنی ندارد؛ از لایه‌ی view با crop مشخص صدا زده می‌شود.
            for variety in variety_qs:
                value, status = self.calculate_smart(region=region, variety=variety)
                if value is not None:
                    rows.append({'label': f"رقم: {variety.crop.name} / {variety.name}", 'value': value, 'status': status})

        return rows


class VariableDefinition(models.Model):
    """۶. متغیرهای ورودی - متصل به محصول و فعالیت. همیشه عددی (چون فقط در فرمول‌های آماری استفاده می‌شوند)."""
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='variables', verbose_name="محصول")
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='indicator_variables',
        verbose_name="فعالیت مرتبط", null=True, blank=True,
    )
    name = models.CharField(max_length=150, verbose_name="عنوان سوال")
    code = models.SlugField(max_length=50, verbose_name="کد پایه (مثلاً: yield)")
    target_indicator = models.ForeignKey(IndicatorDefinition, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_obsolete = models.BooleanField(default=False)

    class Meta:
        verbose_name = "متغیر ورودی"
        verbose_name_plural = "۳. متغیرهای ورودی"
        unique_together = ('crop', 'activity', 'code')
        ordering = ['order']

    def save(self, *args, **kwargs):
        if self.crop and self.crop.slug:
            suffix = f"_{self.crop.slug}"
            if not self.code.endswith(suffix):
                self.code = f"{self.code}{suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.crop.name} | {self.code}"


class ExpertAnswerSubmission(models.Model):
    """۷. ثبت نهایی پاسخ‌ها"""
    STATUS_CHOICES = (('draft', 'پیش‌نویس'), ('submitted', 'ارسال شده'), ('verified', 'تایید شده'))
    company = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name="شرکت")
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name="بخش (لایه ۵ یا بالاتر)")
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, verbose_name="محصول")
    variety = models.ForeignKey(CropVariety, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="رقم محصول")
    expert = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="وضعیت")

    task = models.ForeignKey(
        'accounts.ExpertTask', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submissions', verbose_name="وظیفه مرتبط",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

    class Meta:
        verbose_name = "پاسخ کارشناس"
        verbose_name_plural = "۴. پاسخ‌های ثبت شده"

    def clean(self):
        if self.region and self.region.level < 5:
            raise ValidationError("ثبت پاسخ‌ها صرفاً در سطوح عملیاتی (سطح ۵ به بالا) مجاز است.")


class ExpertAnswerDetail(models.Model):
    """۸. جزئیات مقادیر عددی"""
    submission = models.ForeignKey(ExpertAnswerSubmission, on_delete=models.CASCADE, related_name='details')
    variable = models.ForeignKey(VariableDefinition, on_delete=models.PROTECT)
    value = models.DecimalField(max_digits=15, decimal_places=3, verbose_name="مقدار")

    class Meta:
        verbose_name = "جزئیات پاسخ"
        verbose_name_plural = "۵. جزئیات پاسخ‌ها"


class RegionIndicatorComment(models.Model):
    """
    ۹. تردِ کامنت سلسله‌مراتبی روی یک منطقه (اختیاراً مرتبط با یک شاخص/محصول
    مشخص). نیازمندی: مدیر بالادست (مثلاً مدیر استان) بتواند روی یک منطقه‌ی
    زیرمجموعه (مثلاً یک شهرستان) نظر/هشدار ثبت کند و مسئول همان منطقه
    (یا رده‌های میانی) بتواند پاسخ بدهد؛ گفتگو به شکل یک ترد (parent/reply)
    نگه داشته می‌شود.
    """
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='indicator_comments',
                                verbose_name="منطقه مرتبط")
    indicator = models.ForeignKey(IndicatorDefinition, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="شاخص مرتبط (اختیاری)")
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="محصول مرتبط (اختیاری)")

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                related_name='region_indicator_comments', verbose_name="نویسنده")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='replies', verbose_name="پاسخ به")

    message = models.TextField(verbose_name="متن نظر/پاسخ")
    is_resolved = models.BooleanField(default=False, verbose_name="رسیدگی شده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")

    class Meta:
        verbose_name = "نظر مدیریتی روی منطقه"
        verbose_name_plural = "۶. نظرات مدیریتی مناطق"
        ordering = ['created_at']

    def __str__(self):
        author_name = self.author.get_full_name() if self.author and self.author.get_full_name() else getattr(self.author, 'username', 'حذف‌شده')
        return f"{author_name} -> {self.region.name}: {self.message[:30]}"
