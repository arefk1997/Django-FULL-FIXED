from django.contrib import admin
from django.utils.html import format_html
from .models import Survey, Question, Answer, SurveyFormula, CalculatedResult

class QuestionInline(admin.TabularInline):
    model = Question
    fields = ('text', 'type', 'choices', 'required')
    extra = 1
    classes = ['collapse']  # برای خلوت ماندن صفحه، بخش سوالات قابل جمع شدن است


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_user_display', 'crop_display', 'is_general', 'is_active', 'question_count')
    list_filter = ('target_user_type', 'is_general', 'target_crop', 'is_active', 'company')
    search_fields = ('title', 'company__name')
    autocomplete_fields = ['target_crop', 'company']  # انتخاب سریع با جستجو
    inlines = [QuestionInline]

    fieldsets = (
        ("اطلاعات اصلی", {
            'fields': ('title', 'company', 'description', 'is_active')
        }),
        ("تنظیمات هوشمند (نمایش اختصاصی)", {
            'fields': ('target_user_type', 'target_crop', 'is_general'),
            'description': "در این بخش مشخص کنید این پرسشنامه برای چه کسی و برای چه محصولی نمایش داده شود."
        }),
    )

    def target_user_display(self, obj):
        return obj.get_target_user_type_display()
    target_user_display.short_description = "مخاطب هدف"

    def crop_display(self, obj):
        if obj.target_crop:
            return format_html('<b style="color: #059669;">{}</b>', obj.target_crop.name)
        return "همه محصولات" if obj.is_general else "بدون محصول"
    crop_display.short_description = "محصول مرتبط"

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = "تعداد سوالات"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_id_text', 'survey', 'colored_type', 'required')
    list_filter = ('type', 'survey__target_crop', 'survey')
    search_fields = ('text', 'survey__title')
    readonly_fields = ('live_percentage_analysis',)  # نمایش نمودار درصدها در صفحه ویرایش سوال

    def question_id_text(self, obj):
        return f"[{obj.id}] {obj.text[:50]}"
    question_id_text.short_description = "کد و متن سوال"

    def colored_type(self, obj):
        colors = {
            'text': '#0ea5e9',
            'textarea': '#8b5cf6',
            'number': '#f59e0b',
            'radio': '#10b981',
        }
        color = colors.get(obj.type, '#64748b')
        label = obj.get_type_display()
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, label)
    colored_type.short_description = "نوع سوال"

    def live_percentage_analysis(self, obj):
        """نمایش زنده و شیک آمار فراوانی پاسخ‌ها به درصد (کاملاً بهینه‌شده برای جنگو ۵ و ۶)"""
        if obj.type != 'radio':
            # اصلاح خطای فرمت: متن به عنوان آرگومان مجزا پاس داده شد
            return format_html('<span>{}</span>', "این تحلیل فقط برای سوالات تک انتخابی (گزینه‌ای) در دسترس است.")

        analysis = obj.get_responses_percentage()
        if not analysis:
            # اصلاح خطای فرمت: متن به عنوان آرگومان مجزا پاس داده شد
            return format_html('<span>{}</span>', "هنوز پاسخی برای این سوال ثبت نشده است.")

        # تگ ابتدایی باکس به همراه آرگومان معتبر
        html_output = format_html(
            '<div style="background: #f8fafc; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; max-width: 500px;">'
            '<strong style="color: #0f172a; display:block; margin-bottom: 10px;">📊 آمار فراوانی پاسخ‌ها (به درصد):</strong>'
        )

        for option, percentage in analysis.items():
            row_html = format_html(
                '<div style="margin-bottom: 8px;">'
                '<span style="font-weight: 500; color: #334155;">{}</span>: '
                '<strong style="color: #2563eb;">{}%</strong>'
                '<div style="background: #e2e8f0; border-radius: 4px; height: 8px; width: 100%; margin-top: 4px;">'
                '<div style="background: #3b82f6; height: 8px; border-radius: 4px; width: {}%;"></div>'
                '</div>'
                '</div>',
                option,
                percentage,
                percentage
            )
            # ترکیب امن و گام‌به‌گام رشته‌های HTML برای جلوگیری از شکست تگ‌ها در موتور رندر
            html_output = format_html('{}{}', html_output, row_html)

        html_output = format_html('{}</div>', html_output)
        return html_output
    live_percentage_analysis.short_description = "تحلیل آماری گزینه‌ها"


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_survey', 'short_question', 'short_answer', 'created_at')
    list_filter = ('question__survey', 'created_at')
    search_fields = ('user__username', 'text_answer', 'question__text')
    readonly_fields = ('user', 'question', 'text_answer', 'score_earned', 'created_at')

    def get_survey(self, obj):
        return obj.question.survey.title
    get_survey.short_description = "پرسشنامه"

    def short_question(self, obj):
        return obj.question.text[:40] + "..." if len(obj.question.text) > 40 else obj.question.text
    short_question.short_description = "سوال"

    def short_answer(self, obj):
        return obj.text_answer[:30] + "..." if len(obj.text_answer) > 30 else obj.text_answer
    short_answer.short_description = "پاسخ کاربر"


@admin.register(SurveyFormula)
class SurveyFormulaAdmin(admin.ModelAdmin):
    list_display = ('result_name', 'formula_structure', 'multiplier')
    list_filter = ('variable_a__survey', 'variable_b__survey')
    search_fields = ('result_name', 'variable_a__text', 'variable_b__text')

    def formula_structure(self, obj):
        operators = {'add': '+', 'sub': '-', 'mul': '*', 'div': '/'}
        return format_html(
            '<span style="color: #475569;">سوال <b style="color: #2563eb;">[{}]</b> (<small style="color: #64748b;">{}</small>) '
            '<b style="color: #dc2626; font-size: 1.1rem; padding: 0 4px;">{}</b> '
            'سوال <b style="color: #2563eb;">[{}]</b> (<small style="color: #64748b;">{}</small>)</span>',
            obj.variable_a_id,
            obj.variable_a.survey.title[:20],
            operators.get(obj.operator, '?'),
            obj.variable_b_id,
            obj.variable_b.survey.title[:20]
        )
    formula_structure.short_description = "ساختار محاسبات جامع بین پرسشنامه‌ای"


@admin.register(CalculatedResult)
class CalculatedResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_formula_name', 'formatted_value', 'calculated_at')
    list_filter = ('formula__result_name', 'calculated_at')
    search_fields = ('user__username', 'formula__result_name')
    readonly_fields = ('user', 'formula', 'formatted_value', 'calculated_at')

    def get_formula_name(self, obj):
        return obj.formula.result_name
    get_formula_name.short_description = "شاخص خروجی ترکیبی"

    def formatted_value(self, obj):
        return format_html(
            '<strong style="color: #16a34a; font-size: 1.05rem;">{:.2f}</strong>',
            obj.calculated_value
        )
    formatted_value.short_description = "مقدار نهایی محاسباتی"