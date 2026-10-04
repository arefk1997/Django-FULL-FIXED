from django.db import models
from django.conf import settings
from accounts.models import Company, Activity
from indicators.models import Crop, VariableDefinition  # فرض بر این است مدل متغیر در اندیکاتور وجود دارد

class Survey(models.Model):
    TARGET_CHOICES = (
        ('all', 'عمومی (همه کاربران)'),
        ('farmer', 'فقط کشاورزان'),
        ('official', 'فقط پرسنل اداری / کارشناسان'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='surveys', verbose_name="شرکت/سازمان متولی", null=True, blank=True)
    title = models.CharField(max_length=200, verbose_name="عنوان پرسشنامه")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات/راهنمای پاسخ‌دهی")
    target_user_type = models.CharField(max_length=15, choices=TARGET_CHOICES, default='all', verbose_name="مخاطب هدف")
    target_crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True, related_name='crop_surveys', verbose_name="مخصوص محصول خاص")
    is_general = models.BooleanField(default=False, verbose_name="پرسشنامه عمومی (بدون وابستگی به محصول)")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعالیت")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ساخت")

    class Meta:
        verbose_name = "پرسشنامه"
        verbose_name_plural = "۱. مدیریت پرسشنامه‌ها"

    def __str__(self):
        type_label = self.target_crop.name if self.target_crop else ("عمومی" if self.is_general else "نامشخص")
        return f"{self.title} ({type_label})"


class Question(models.Model):
    TYPE_CHOICES = (
        ('text', 'متن کوتاه'),
        ('textarea', 'متن طولانی'),
        ('number', 'عدد'),
        ('radio', 'تک انتخابی (گزینه‌ای)'),
    )
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions', verbose_name="پرسشنامه")
    text = models.CharField(max_length=500, verbose_name="متن سوال")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text', verbose_name="نوع سوال")
    choices = models.CharField(max_length=500, blank=True, null=True, verbose_name="گزینه‌ها", help_text="گزینه‌ها را با ویرگول (,) جدا کنید.")
    required = models.BooleanField(default=True, verbose_name="اجباری")

    class Meta:
        verbose_name = "سوال"
        verbose_name_plural = "۲. سوالات"

    def __str__(self):
        return f"سوال {self.id}: {self.text[:30]}"

    def get_choices_dict(self):
        if not self.choices:
            return []
        raw_items = self.choices.replace('،', ',').split(',')
        return [{'text': item.strip()} for item in raw_items if item.strip()]

    def get_responses_percentage(self):
        if self.type != 'radio':
            return {}
        total_answers = self.answers.count()
        choices_list = self.get_choices_dict()
        if total_answers == 0:
            return {c['text']: 0.0 for c in choices_list}
        analysis = {}
        for c in choices_list:
            count = self.answers.filter(text_answer=c['text']).count()
            analysis[c['text']] = round((count / total_answers) * 100, 1)
        return analysis


class Answer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="پاسخ‌دهنده")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name="سوال")
    text_answer = models.TextField(verbose_name="پاسخ ثبت شده")
    score_earned = models.IntegerField(default=0, verbose_name="امتیاز کسب شده (منسوخ)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")

    class Meta:
        unique_together = ('user', 'question')
        verbose_name = "پاسخ"
        verbose_name_plural = "۳. بانک پاسخ‌ها"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # مهار داینامیک فرمول‌ها بدون ایجاد ریلیشن مستقیم معکوس
        dependent_formulas = SurveyFormula.objects.filter(
            models.Q(variable_a=self.question) | models.Q(variable_b=self.question)
        )
        for formula in dependent_formulas:
            formula.run_calculation(self.user)

    def __str__(self):
        return f"{self.user.username} -> {self.question.text[:20]}"


class SurveyFormula(models.Model):
    OPERATOR_CHOICES = (('add', 'جمع (+)'), ('sub', 'تفریق (-)'), ('mul', 'ضرب (*)'), ('div', 'تقسیم (/)'))
    result_name = models.CharField(max_length=150, verbose_name="نام متغیر خروجی ترکیبی")
    variable_a = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='formula_variables_a', verbose_name="سوال اول (متغیر A)")
    operator = models.CharField(max_length=10, choices=OPERATOR_CHOICES, verbose_name="عملگر ریاضی")
    variable_b = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='formula_variables_b', verbose_name="سوال دوم (متغیر B)")
    multiplier = models.FloatField(default=1.0, verbose_name="ضریب نهایی تبدیل واحد")

    class Meta:
        verbose_name = "فرمول محاسباتی"
        verbose_name_plural = "۴. فرمول‌های محاسباتی"

    def run_calculation(self, user):
        try:
            ans_a = Answer.objects.filter(user=user, question=self.variable_a).latest('created_at')
            ans_b = Answer.objects.filter(user=user, question=self.variable_b).latest('created_at')
            val_a, val_b = float(ans_a.text_answer), float(ans_b.text_answer)

            if self.operator == 'add': res = val_a + val_b
            elif self.operator == 'sub': res = val_a - val_b
            elif self.operator == 'mul': res = val_a * val_b
            elif self.operator == 'div': res = val_a / val_b if val_b != 0 else 0
            else: res = 0

            final_value = res * self.multiplier
            CalculatedResult.objects.update_or_create(user=user, formula=self, defaults={'calculated_value': final_value})
        except (Answer.DoesNotExist, ValueError):
            pass

    def __str__(self):
        return f"{self.result_name} [سوال {self.variable_a_id} به {self.variable_b_id}]"


class CalculatedResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="پاسخ‌دهنده")
    formula = models.ForeignKey(SurveyFormula, on_delete=models.CASCADE, related_name='results', verbose_name="فرمول اعمال شده")
    calculated_value = models.FloatField(verbose_name="مقدار نهایی محاسبه شده")
    calculated_at = models.DateTimeField(auto_now=True, verbose_name="زمان محاسبه")

    class Meta:
        unique_together = ('user', 'formula')
        verbose_name = "نتیجه تحلیل عددی"
        verbose_name_plural = "۵. نتایج تحلیل‌های عددی"


# --- لایه متولد شده مدل‌های مدیریتی عارضه‌یابی و اتصال KPI ---

class QuestionAnalytics(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='analytics', verbose_name="سوال مربوطه")
    total_responses = models.IntegerField(default=0, verbose_name="کل پاسخ‌ها")
    satisfaction_index = models.FloatField(default=0.0, verbose_name="شاخص رضایت CSI")
    numerical_metrics = models.JSONField(default=dict, blank=True, verbose_name="شاخص‌های توصیفی عددی")
    choice_metrics = models.JSONField(default=dict, blank=True, verbose_name="متریک‌های فراوانی گزینه‌ها")
    text_metrics = models.JSONField(default=dict, blank=True, verbose_name="خروجی متنی هوش مصنوعی")

    class Meta:
        verbose_name = "تحلیل آماری سوال"
        verbose_name_plural = "۶. داشبورد تحلیلی سوالات"


class SurveyKPIBinding(models.Model):
    BINDING_TYPES = (
        ('question_csi', 'شاخص رضایت سوال (CSI)'),
        ('question_mean', 'میانگین حسابی پاسخ عددی سوال'),
        ('formula_output', 'خروجی فرمول ترکیبی محاسباتی'),
    )
    result_name = models.CharField(max_length=150, verbose_name="عنوان نگاشت")
    binding_type = models.CharField(max_length=30, choices=BINDING_TYPES, verbose_name="نوع دیتای تزریقی")
    source_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="سوال منبع")
    source_formula = models.ForeignKey(SurveyFormula, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="فرمول منبع")
    target_variable = models.ForeignKey(VariableDefinition, on_delete=models.CASCADE, verbose_name="متغیر مقصد در شاخص‌ها")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت اتصال")

    class Meta:
        verbose_name = "اتصال پرسشنامه به KPI"
        verbose_name_plural = "۷. موتور همگام‌سازی شاخص‌ها"