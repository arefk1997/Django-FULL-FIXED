"""
accounts/signals.py

مشکل قبلی: سیگنال روی هر post_save که is_approved=True باشد اجرا می‌شد.
چون login() هم user.save(update_fields=['last_login']) صدا می‌زند، هر بار
که یک کاربر تاییدشده وارد سیستم می‌شد، دوباره ایمیل «حساب شما تایید شد»
برایش ارسال می‌شد.

راه‌حل: با pre_save مقدار قبلی is_approved را از دیتابیس می‌خوانیم و در
post_save فقط وقتی ایمیل می‌فرستیم که واقعاً از False به True تغییر کرده
باشد (transition، نه صرفاً «True است»).
"""
import logging

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from .models import CustomUser

logger = logging.getLogger(__name__)

_APPROVAL_FLAG_ATTR = '_was_approved_before_save'


@receiver(pre_save, sender=CustomUser)
def _capture_previous_approval_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            previous = CustomUser.objects.only('is_approved').get(pk=instance.pk)
            setattr(instance, _APPROVAL_FLAG_ATTR, previous.is_approved)
        except CustomUser.DoesNotExist:
            setattr(instance, _APPROVAL_FLAG_ATTR, False)
    else:
        setattr(instance, _APPROVAL_FLAG_ATTR, False)


@receiver(post_save, sender=CustomUser)
def notify_user_on_approval(sender, instance, created, **kwargs):
    was_approved_before = getattr(instance, _APPROVAL_FLAG_ATTR, False)

    # فقط وقتی ایمیل بفرست که تازه (در همین save) از حالت تاییدنشده به
    # تاییدشده تغییر کرده باشد - نه روی هر save بعدی (مثل لاگین).
    just_got_approved = (not created) and instance.is_approved and not was_approved_before
    if not just_got_approved:
        return

    if not instance.email:
        logger.warning("کاربر %s ایمیل ندارد؛ اعلان تایید ارسال نشد.", instance.username)
        return

    try:
        subject = 'حساب کاربری شما تایید شد'
        message = (
            f'سلام {instance.username} عزیز،\n'
            'حساب شما تایید شد و هم‌اکنون می‌توانید مزرعه خود را ثبت کنید.'
        )
        send_mail(subject, message, None, [instance.email])  # None → DEFAULT_FROM_EMAIL از settings
    except Exception:
        # لاگ کامل با traceback به‌جای print - تا در production قابل پیگیری باشد
        logger.exception("ارسال ایمیل تایید برای کاربر %s با خطا مواجه شد.", instance.username)

    # ارسال پیامک (در صورت نیاز): یک سرویس SMS جدا (مثلاً services/sms.py) بسازید
    # و به‌جای درخواست همزمان HTTP داخل سیگنال، آن را به یک Celery task بسپارید
    # تا در صورت کندی یا خطای سرویس پیامک، ذخیره‌ی کاربر کند/ناموفق نشود.
