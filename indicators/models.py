"""
indicators/models.py

تغییرات اصلی:
- eval() خام با safe_eval_formula (indicators/safe_eval.py) جایگزین شد؛
  دیگر امکان دسترسی به اشیای داخلی پایتون یا اجرای کد دلخواه وجود ندارد.
- variable__code__icontains=db_code به variable__code=db_code تبدیل شد.
  چون VariableDefinition.save() همیشه پسوند _{crop.slug} را دقیقاً به کد
  اضافه می‌کند، جستجوی زیررشته‌ای (icontains) باعث می‌شد کدهایی که فقط بخشی
  از نامشان مشترک است (مثلاً yield_wheat و yield_wheat_extra) با هم قاطی
  شوند و مقدار شاخص اشتباه محاسبه شود.
"""
import re
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Avg, Max, Min, Sum
from accounts.models import Company, Region, Activity

from .safe_eval import safe_eval_formula, UnsafeExpressionError


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


class IndicatorDefinition(models.Model):
    """۵. تعریف شاخص‌ها با پشتیبانی از فرمول‌های شرطی و اعتبارسنجی متغیرها"""
    LEVEL_CHOICES = (
        (1, 'ملی (ستاد)'), (2, 'حوضه آبریز'), (3, 'استانی'), (4, 'شهرستانی'), (5, 'بخش / مزرعه'),
    )
    SCOPE_CHOICES = (
        ('single', 'تک محصولی'), ('category', 'گروه محصولات (دسته)'),
        ('family', 'خانواده گیاهی'), ('all', 'عمومی (تمام محصولات)'),
    )

    name = models.CharField(max_length=200, verbose_name="نام شاخص")
    calculation_level = models.IntegerField(choices=LEVEL_CHOICES, default=5, verbose_name="سطح محاسبه")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='single', verbose_name="دامنه شمول")
    target_category = models.ForeignKey(CropCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                         verbose_name="دسته هدف")
    formula = models.CharField(max_length=500, null=True, blank=True, verbose_name="فرمول (کد عمومی)")
    unit = models.CharField(max_length=50, blank=True, verbose_name="واحد اندازه‌گیری")

    class Meta:
        verbose_name = "تعریف شاخص"
        verbose_name_plural = "۲. تعریف شاخص‌ها"

    def __str__(self):
        return self.name

    def clean(self):
        """اعتبارسنجی فرمول: چک کردن وجود متغیرها + ساختار امن بودن، قبل از ذخیره."""
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

    def _get_subregion_ids(self, reg_obj):
        # اصلاح شد: به‌جای پیمایش بازگشتی با یک کوئری به ازای هر گره، حالا از
        # تابع مشترک accounts.tree_utils.get_subtree_ids استفاده می‌شود (نگاه
        # کنید به توضیح کامل در accounts/tree_utils.py).
        from accounts.tree_utils import get_subtree_ids
        return get_subtree_ids(Region, reg_obj.id)

    def calculate_smart(self, region=None, crop=None, variety=None):
        if not self.formula:
            return None, "بدون فرمول"

        raw_codes = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', self.formula)
        context = {}
        missing_vars = []
        keywords = ['if', 'else', 'and', 'or', 'not', 'min', 'max', 'round', 'abs',
                    'sqrt', 'floor', 'ceil', 'True', 'False']

        if self.calculation_level > 1 and region:
            target_region_ids = self._get_subregion_ids(region)
        elif region:
            target_region_ids = [region.id]
        else:
            target_region_ids = []

        for raw_code in raw_codes:
            if raw_code in keywords:
                continue

            if self.scope == 'single' and crop:
                db_code = f"{raw_code}_{crop.slug}"
            else:
                db_code = raw_code

            # اصلاح شد: مطابقت دقیق به‌جای icontains. چون کد متغیر همیشه با
            # پسوند slug محصول دقیقاً یکسان ساخته می‌شود (نگاه کنید به
            # VariableDefinition.save)، جستجوی زیررشته‌ای صحیح نیست و باعث
            # ترکیب داده‌ی متغیرهای نامرتبط با نام مشابه می‌شد.
            queryset = ExpertAnswerDetail.objects.filter(
                variable__code=db_code,
                submission__status='verified',
            )

            if target_region_ids:
                queryset = queryset.filter(submission__region_id__in=target_region_ids)

            if variety:
                queryset = queryset.filter(submission__variety=variety)
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


class VariableDefinition(models.Model):
    """۶. متغیرهای ورودی - متصل به محصول و فعالیت"""
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='variables', verbose_name="محصول")
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name='indicator_variables',
        verbose_name="فعالیت مرتبط", null=True, blank=True,
    )
    name = models.CharField(max_length=150, verbose_name="عنوان سوال")
    code = models.SlugField(max_length=50, verbose_name="کد پایه (مثلاً: yield)")
    field_type = models.CharField(max_length=20, default='number', verbose_name="نوع فیلد")
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

    # اضافه شد: پیوند مستقیم به ExpertTask. قبلاً تایید نهایی یک تسک با
    # filter(crop=..., expert=...) انجام می‌شد که همه‌ی submissionهای آن
    # کارشناس برای آن محصول را verified می‌کرد (حتی submissionهای مربوط به
    # تسک‌های دیگر). با این فیلد، accounts.views.review_task می‌تواند دقیقاً
    # همان submission مرتبط با همان task را تایید کند.
    # null=True برای سازگاری با داده‌ی قدیمی: submissionهای قبل از این تغییر
    # task خالی خواهند داشت و رفتار قبلی (fallback بر اساس crop+expert) برای
    # آن‌ها در کد حفظ شده است.
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
