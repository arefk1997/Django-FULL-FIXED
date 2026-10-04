from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Answer

@receiver(post_save, sender=Answer)
def trigger_survey_analytics_pipeline(sender, instance, created, **kwargs):
    """شنونده رویداد ثبت پاسخ برای هدایت داده به خط لوله Celery به صورت کاملاً امن"""
    if created:
        # ایمپورت محلی برای شکستن حلقه تداخل کدهای دیتابیس و سلری
        from .tasks import task_process_question_analytics
        task_process_question_analytics.delay(instance.question_id)