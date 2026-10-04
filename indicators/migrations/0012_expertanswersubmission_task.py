# به‌صورت دستی نوشته شده (به همان دلیل migration 0025 در accounts - نگاه کنید
# به کامنت ابتدای آن فایل). این migration باید بعد از
# accounts/migrations/0025_review_fields_and_cleanup اجرا شود چون
# ExpertTask در آن migration تغییر کرده (هر چند این فیلد فقط به مدل ExpertTask
# اشاره می‌کند و به فیلدهای تغییریافته‌اش وابسته نیست، dependency صریح برای
# ایمنی و ترتیب صحیح نگه داشته شده).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_review_fields_and_cleanup"),
        ("indicators", "0011_alter_expertanswersubmission_region_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="expertanswersubmission",
            name="task",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submissions",
                to="accounts.experttask",
                verbose_name="وظیفه مرتبط",
            ),
        ),
    ]
