# اطمینان از بارگذاری celery app به محض بالا آمدن جنگو، تا دکوراتور
# shared_task در surveys/tasks.py بتواند به این app متصل شود.
from .celery import app as celery_app

__all__ = ('celery_app',)
