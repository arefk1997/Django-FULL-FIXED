from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # این import قبلاً وجود نداشت، پس signals.py هیچ‌وقت واقعاً بارگذاری
        # و ثبت نمی‌شد. بدون آن، @receiver در signals.py صرفاً تعریف می‌شود
        # ولی به post_save هیچ‌وقت وصل نمی‌شود.
        import accounts.signals  # noqa: F401
