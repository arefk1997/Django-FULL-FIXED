from django.apps import AppConfig


class SurveysConfig(AppConfig):
    name = 'surveys'

    def ready(self):
        # اصلاح شد: دقیقاً همان باگ accounts/apps.py اینجا هم وجود داشت.
        # بدون این import، signals.py هیچ‌وقت واقعاً import نمی‌شد، پس
        # trigger_survey_analytics_pipeline هیچ‌وقت به post_save وصل نمی‌شد
        # و با هر پاسخ جدید، هیچ تسک Celery‌ای صف‌بندی نمی‌شد.
        import surveys.signals  # noqa: F401
