"""
ترمیم والد (parent) مناطق بعد از import_iran.py

- ایمن برای اجرای چندباره (idempotent)
- والد را بر اساس «قرار گرفتن نقطه‌ی داخلی پولیگون فرزند در پولیگون والد» پیدا می‌کند،
  نه بر اساس نام؛ بنابراین مشکل نام‌های تکراری (مثلاً بخش‌های هم‌نام در شهرستان‌های
  مختلف) پیش نمی‌آید.

اجرا:  python repair_region_hierarchy.py
قبل از اجرا: ROOT_ID و نام ماژول settings را مطابق پروژه تنظیم کنید.
"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_proj.settings')  # نام پروژه خودتان
django.setup()

from django.db import transaction

from accounts.models import Region

ROOT_ID = 1            # شناسه‌ی رکورد «ایران» (همان parent.id در پاسخ هیت‌مپ)
PROVINCE_LEVEL = 3
LEVEL_CHAIN = [(4, 3), (5, 4), (6, 5)]   # (سطح فرزند، سطح والد)


def diagnose():
    print("سطح | تعداد | بدون والد | بدون geom")
    for lvl in sorted(set(Region.objects.values_list('level', flat=True))):
        qs = Region.objects.filter(level=lvl)
        print(f"{lvl:>4} | {qs.count():>5} | {qs.filter(parent__isnull=True).count():>9} | "
              f"{qs.filter(geom__isnull=True).count():>9}")


@transaction.atomic
def link_provinces():
    root = Region.objects.get(id=ROOT_ID)
    n = Region.objects.filter(level=PROVINCE_LEVEL).exclude(parent=root).update(parent=root)
    print(f"استان‌های متصل‌شده به «{root.name}»: {n}")


@transaction.atomic
def relink(child_level, parent_level):
    parents = Region.objects.filter(level=parent_level, geom__isnull=False)
    to_update, unmatched = [], []
    children = Region.objects.filter(level=child_level, geom__isnull=False)
    for child in children.iterator(chunk_size=500):
        point = child.geom.point_on_surface           # همیشه داخل پولیگون است (برخلاف centroid)
        parent = parents.filter(geom__contains=point).only('id').first()
        if parent is None:
            unmatched.append(child.name)
        elif child.parent_id != parent.id:
            child.parent_id = parent.id
            to_update.append(child)
    Region.objects.bulk_update(to_update, ['parent'], batch_size=500)
    print(f"سطح {child_level}: {len(to_update)} والد اصلاح شد، {len(unmatched)} بدون تطبیق")
    if unmatched:
        print("   نمونه‌ی بدون تطبیق:", unmatched[:10])


if __name__ == "__main__":
    print("--- قبل ---")
    diagnose()
    link_provinces()
    for child_lvl, parent_lvl in LEVEL_CHAIN:
        relink(child_lvl, parent_lvl)
    print("--- بعد ---")
    diagnose()