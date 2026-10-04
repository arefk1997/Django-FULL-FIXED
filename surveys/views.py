"""
surveys/views.py

تغییرات:
- export_answers_excel قبلاً فقط `pass` بود و None برمی‌گرداند که در جنگو
  باعث ValueError/500 می‌شود (یک ویو باید همیشه HttpResponse برگرداند). حالا
  با openpyxl یک خروجی اکسل واقعی از پاسخ‌ها می‌سازد.
- نام قالب‌های render شده با فایل‌های واقعاً موجود در
  surveys/templates/surveys/ هماهنگ شد (survey_form.html و report.html به‌جای
  submit_survey.html و survey_report.html که وجود نداشتند). یک survey_list.html
  حداقلی هم اضافه شد.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import Question, QuestionAnalytics, Survey, Answer
from .serializers import QuestionAnalyticsSerializer
from .forms import DynamicSurveyForm


def survey_list(request):
    surveys = Survey.objects.filter(is_active=True)
    return render(request, 'surveys/survey_list.html', {'surveys': surveys})


def submit_survey(request, survey_id):
    survey = get_object_or_404(Survey, id=survey_id)
    if request.method == 'POST':
        form = DynamicSurveyForm(request.POST, survey_id=survey_id)
        if form.is_valid():
            form.save_answers(request.user)
            messages.success(request, "پاسخ‌های شما با موفقیت ثبت و به صف پردازش هدایت شد.")
            return redirect('surveys:survey_list')
    else:
        form = DynamicSurveyForm(survey_id=survey_id)
    # نکته: قبلاً 'surveys/submit_survey.html' که وجود نداشت رندر می‌شد؛
    # فایل واقعی در پروژه survey_form.html نام دارد.
    return render(request, 'surveys/survey_form.html', {'form': form, 'survey': survey})


def survey_report(request):
    # نکته: قبلاً 'surveys/survey_report.html' که وجود نداشت رندر می‌شد؛
    # فایل واقعی report.html نام دارد.
    return render(request, 'surveys/report.html')


def export_answers_excel(request):
    """
    خروجی اکسل از پاسخ‌های ثبت‌شده.

    نکته‌ی امنیتی: این ویو در حال حاضر عمومی است (بدون @login_required)؛ اگر
    باید فقط برای کاربران خاص در دسترس باشد، @login_required و/یا فیلتر روی
    company کاربر را اضافه کنید.
    """
    try:
        from openpyxl import Workbook
    except ImportError:
        return HttpResponse(
            "کتابخانه‌ی openpyxl نصب نیست. با «pip install openpyxl» نصب کنید.",
            status=500,
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "پاسخ‌ها"
    ws.append(["کاربر", "سوال", "پاسخ", "تاریخ ثبت"])

    answers = Answer.objects.select_related('user', 'question').order_by('-created_at')[:5000]
    for ans in answers:
        ws.append([
            ans.user.username,
            ans.question.text,
            ans.text_answer,
            ans.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=survey_answers.xlsx'
    wb.save(response)
    return response


class SurveyAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'], url_path='question-analysis')
    def get_question_analytics(self, request, pk=None):
        try:
            analytics = QuestionAnalytics.objects.get(question_id=pk)
            serializer = QuestionAnalyticsSerializer(analytics)
            return Response(serializer.data)
        except QuestionAnalytics.DoesNotExist:
            return Response({'error': 'داده‌های تحلیلی هنوز پردازش نشده‌اند.'}, status=404)
