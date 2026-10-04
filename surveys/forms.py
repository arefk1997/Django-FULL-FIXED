from django import forms
from .models import Question


class DynamicSurveyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # دریافت survey_id از ویو برای استخراج سوالات همان پرسشنامه
        survey_id = kwargs.pop('survey_id', None)
        super().__init__(*args, **kwargs)

        if survey_id:

            questions = Question.objects.filter(survey_id=survey_id).order_by('id')

            for q in questions:
                field_name = f'question_{q.id}'

                # ۱. سوال متنی کوتاه
                if q.type == 'text':
                    self.fields[field_name] = forms.CharField(label=q.text, required=q.required)

                # ۲. سوال متنی طولانی
                elif q.type == 'textarea':
                    self.fields[field_name] = forms.CharField(
                        label=q.text,
                        widget=forms.Textarea(attrs={'rows': 3}),
                        required=q.required
                    )

                # ۳. سوال عددی
                elif q.type == 'number':
                    self.fields[field_name] = forms.IntegerField(label=q.text, required=q.required)

                # ۴. سوال تک‌انتخابی (رادیویی) با مدیریت متد جدید امتیازدهی
                elif q.type == 'radio':
                    choices_data = q.get_choices_dict()
                    choices_list = [(c['text'], c['text']) for c in choices_data]

                    self.fields[field_name] = forms.ChoiceField(
                        label=q.text,
                        choices=choices_list,
                        widget=forms.RadioSelect,
                        required=q.required
                    )

                # اعمال استایل‌های Tailwind CSS برای زیبایی رابط کاربری
                if field_name in self.fields:
                    if q.type != 'radio':
                        self.fields[field_name].widget.attrs.update({
                            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none mb-4 shadow-sm transition-all',
                            'placeholder': 'پاسخ خود را اینجا بنویسید...'
                        })
                    else:
                        # استایل اختصاصی برای گزینه‌های رادیویی
                        self.fields[field_name].widget.attrs.update({'class': 'flex flex-col gap-2 mb-4'})

    def save_answers(self, user):
        """
        متد کمکی برای ذخیره سریع و خودکار پاسخ‌ها به همراه امتیاز تحلیل در ویو
        """
        from .models import Answer
        for field_name, value in self.cleaned_data.items():
            question_id = field_name.split('_')[1]
            question = Question.objects.get(id=question_id)

            Answer.objects.update_or_create(
                user=user,
                question=question,
                defaults={'text_answer': value}
            )