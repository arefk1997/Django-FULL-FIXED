from celery import shared_task
from .services import QuestionAnalyticsService
from .ai_analytics import AISurveyAnalyticEngine
from .models import Question, SurveyKPIBinding, QuestionAnalytics
from .kpi_connector import KPIMappingService


@shared_task(queue='analytics', max_retries=3)
def task_process_question_analytics(question_id):
    """تسک ناهمگام برای اجرای پردازش‌های عددی و آماری هر سوال"""
    QuestionAnalyticsService.run_full_analysis(question_id)

    # اگر سوال متنی تشریحی بود، تحلیل هوش مصنوعی را نیز خط‌کشی کن
    question = Question.objects.get(id=question_id)
    if question.type in ['text', 'textarea']:
        ai_data = AISurveyAnalyticEngine.extract_keywords_and_complaints(question_id)
        analytics, _ = QuestionAnalytics.objects.get_or_create(question=question)
        analytics.text_metrics = ai_data
        analytics.save()

    # فعال‌سازی زنجیره‌ای به‌روزرسانی شاخص‌های KPI متصل به این سوال
    bindings = SurveyKPIBinding.objects.filter(source_question_id=question_id, is_active=True)
    for binding in bindings:
        task_update_kpi_value.delay(binding.id)


@shared_task(queue='kpis')
def task_update_kpi_value(binding_id):
    """تسک اختصاصی تزریق مقادیر به متغیرهای KPI مقصد"""
    KPIMappingService.sync_binding_to_kpi(binding_id)