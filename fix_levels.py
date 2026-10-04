import os
import django

# تنظیمات محیط جنگو
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_proj.settings')  # نام پروژه خود را چک کنید
django.setup()

from accounts.models import Region


def migrate_levels():
    print("در حال اصلاح سطوح مدیریت آب...")

    # ۱. بخش‌ها (قدیم ۳ بود، الان باید ۵ بشوند)
    # اول از لول بالا شروع می‌کنیم که تداخل ایجاد نشود
    Region.objects.filter(level=3).update(level=5)
    print("بخش‌ها به سطح ۵ منتقل شدند.")

    # ۲. شهرستان‌ها (قدیم ۲ بود، الان باید ۴ بشوند)
    Region.objects.filter(level=2).update(level=4)
    print("شهرستان‌ها به سطح ۴ منتقل شدند.")

    # ۳. استان‌ها (قدیم ۱ بود، الان باید ۳ بشوند)
    Region.objects.filter(level=1).update(level=3)
    print("استان‌ها به سطح ۳ منتقل شدند.")

    print("✅ اصلاح سطوح با موفقیت انجام شد.")


if __name__ == "__main__":
    migrate_levels()