"""
my_proj/celery.py

قبلاً این فایل اصلاً وجود نداشت، در حالی که surveys/tasks.py از
`@shared_task` و `.delay(...)` استفاده می‌کرد (که celery و redis هم در
requirements.txt نبودند - رفع شد). بدون این فایل و بدون وایرینگ در
my_proj/__init__.py، حتی اگر celery نصب می‌شد، هیچ Celery app ای برای اجرای
این تسک‌ها وجود نداشت.

اجرا در محیط توسعه:
    celery -A my_proj worker -l info -Q analytics,kpis
(نیازمند یک broker در حال اجرا، مثلا redis: redis-server)
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_proj.settings')

app = Celery('my_proj')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
