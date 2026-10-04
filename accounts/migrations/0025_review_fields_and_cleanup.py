# این migration به‌صورت دستی نوشته شده، چون در محیطی که این اصلاحیه آماده
# شد Django/GDAL/PostGIS نصب نبود و امکان اجرای واقعی `makemigrations` وجود
# نداشت. قبل از اعمال روی دیتابیس واقعی:
#   1) از دیتابیس بک‌آپ بگیرید.
#   2) این فایل را با `python manage.py makemigrations --check --dry-run`
#      مقابل مدل‌های فعلی خودتان بررسی کنید؛ اگر Django چیز دیگری هم تشخیص
#      داد (مثلاً به‌خاطر تفاوت جزئی نسخه‌ی Django)، یک migration تکمیلی با
#      `makemigrations` بسازید تا state کاملاً هم‌تراز شود.
#
# ترتیب عملیات عمداً این‌طور است: دلیل رد (rejection_reason) قبل از حذف
# فیلد، به manager_comment منتقل می‌شود تا هیچ داده‌ی تاریخی گم نشود.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_rejection_reason_to_comment(apps, schema_editor):
    ExpertTask = apps.get_model('accounts', 'ExpertTask')
    for task in ExpertTask.objects.exclude(rejection_reason__isnull=True).exclude(rejection_reason__exact=''):
        if task.manager_comment:
            task.manager_comment = f"{task.manager_comment}\n[دلیل رد قدیمی]: {task.rejection_reason}"
        else:
            task.manager_comment = task.rejection_reason
        task.save(update_fields=['manager_comment'])


def noop_reverse(apps, schema_editor):
    # این انتقال داده برگشت‌پذیر نیست (چون manager_comment ممکن است از قبل
    # هم مقدار داشته باشد)؛ عمداً خالی گذاشته شده است.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_experttask_created_at_experttask_rejection_reason"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ۱. ابتدا داده‌ی rejection_reason را به manager_comment منتقل کن
        migrations.RunPython(copy_rejection_reason_to_comment, noop_reverse),

        # ۲. فیلدهای جدید نظارتی
        migrations.AddField(
            model_name="experttask",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="زمان بررسی"),
        ),
        migrations.AddField(
            model_name="experttask",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_tasks",
                to=settings.AUTH_USER_MODEL,
                verbose_name="بررسی‌کننده",
            ),
        ),

        # ۳. حذف فیلد تکراری (بعد از انتقال داده در مرحله‌ی ۱)
        migrations.RemoveField(
            model_name="experttask",
            name="rejection_reason",
        ),

        # ۴. سخت‌گیرتر شدن حذف کارشناس: دیگر حذف کاربر، تاریخچه‌ی وظایف را
        # پاک نمی‌کند (CASCADE -> PROTECT)
        migrations.AlterField(
            model_name="experttask",
            name="expert",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assigned_tasks",
                to=settings.AUTH_USER_MODEL,
                verbose_name="مسئول فعلی",
            ),
        ),

        # ۵. یکتا شدن کد ملی + اعتبارسنجی رقم کنترل (منطق clean/validator در
        # accounts/models.py، این‌جا فقط سطح دیتابیس/ستون تغییر می‌کند)
        #
        # هشدار: اگر داده‌ی فعلی شما چند کاربر را با یک national_code تکراری
        # دارد (مثلاً داده‌ی تستی یا کد ملی خالی ثبت‌شده به‌جای NULL)، این
        # ALTER با خطای unique constraint شکست می‌خورد. قبل از اجرا با یک
        # کوئری مثل زیر بررسی کنید:
        #   SELECT national_code, COUNT(*) FROM accounts_customuser
        #   WHERE national_code IS NOT NULL AND national_code != ''
        #   GROUP BY national_code HAVING COUNT(*) > 1;
        migrations.AlterField(
            model_name="customuser",
            name="national_code",
            field=models.CharField(
                blank=True, max_length=10, null=True, unique=True, verbose_name="کد ملی"
            ),
        ),
    ]
