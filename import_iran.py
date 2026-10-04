import os
import sys
import zipfile
import tempfile
import shutil
import django

# ۱. تنظیمات محیطی ویندوز برای GDAL
base_venv = sys.prefix
osgeo_path = os.path.join(base_venv, 'Lib', 'site-packages', 'osgeo')
if os.path.exists(osgeo_path):
    os.environ['PATH'] = osgeo_path + ';' + os.environ.get('PATH', '')
    os.environ['PROJ_LIB'] = os.path.join(osgeo_path, 'data', 'proj')
    os.environ['GDAL_DATA'] = os.path.join(osgeo_path, 'data', 'gdal')

# ۲. راه‌اندازی جنگو
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Django_Test.settings')
django.setup()

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from accounts.models import Region


def get_field_val(feature, possible_names):
    """جستجوی ایمن نام‌ها از میان اسامی احتمالی ستون‌ها"""
    for name in possible_names:
        try:
            val = feature.get(name)
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            continue
    return None


def process_geometry(feature):
    """اصلاح و استانداردسازی هندسه"""
    geom = GEOSGeometry(feature.geom.wkt, srid=4326)

    # اصلاح جابجایی محورها (حل مشکل آفریقا)
    if geom.centroid.x < 44:
        new_polys = []
        iter_geom = geom if isinstance(geom, MultiPolygon) else [geom]
        for poly in iter_geom:
            new_rings = [[(p[1], p[0]) for p in ring] for ring in poly]
            new_polys.append(Polygon(*new_rings))
        geom = MultiPolygon(*new_polys)
        geom.srid = 4326

    if isinstance(geom, Polygon):
        geom = MultiPolygon(geom)

    if not geom.valid:
        geom = geom.make_valid()

    return geom


def run_multi_layer_import(zip_path):
    print("--- شروع واردسازی تقسیمات کشوری از فایل‌های ۴ گانه ---")
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(temp_dir)

        # ترتیب پردازش: اول استان، سپس شهرستان، بعد بخش و در نهایت دهستان
        layers_config = [
            {'file': 'Ostan.shp', 'level': 3, 'name_fields': ['Ostan', 'OSTAN', 'ProvincNam', 'NAME_1', 'NAME']},
            {'file': 'Shahrestan.shp', 'level': 4,
             'name_fields': ['Shahrestan', 'SHAHRESTAN', 'CityName', 'NAME_2', 'NAME'],
             'parent_fields': ['Ostan', 'OSTAN', 'ProvincNam']},
            {'file': 'Bakhsh.shp', 'level': 5, 'name_fields': ['Bakhsh', 'BAKHSH', 'DistricNam', 'NAME_3', 'NAME'],
             'parent_fields': ['Shahrestan', 'SHAHRESTAN', 'CityName']},
            {'file': 'Dehestan.shp', 'level': 6, 'name_fields': ['Dehestan', 'DEHESTAN', 'NAME_4', 'NAME'],
             'parent_fields': ['Bakhsh', 'BAKHSH', 'DistricNam']}
        ]

        for config in layers_config:
            # یافتن فایل مربوطه در پوشه استخراج شده
            target_shp = None
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower() == config['file'].lower():
                        target_shp = os.path.join(root, f)
                        break

            if not target_shp:
                print(f"⚠️ فایل {config['file']} پیدا نشد، لایه بعدی بررسی می‌شود.")
                continue

            print(f"\n📂 در حال پردازش لایه {config['file']} (سطح {config['level']})...")
            ds = DataSource(target_shp)
            layer = ds[0]

            count = 0
            for feature in layer:
                reg_name = get_field_val(feature, config['name_fields'])
                if not reg_name:
                    continue

                parent_region = None
                # پیدا کردن والد (Parent) بر اساس فیلدهای بالادستی
                if 'parent_fields' in config:
                    parent_name = get_field_val(feature, config['parent_fields'])
                    if parent_name:
                        parent_region = Region.objects.filter(
                            name=parent_name,
                            level=config['level'] - 1
                        ).first()

                geom = process_geometry(feature)

                # ذخیره یا بروزرسانی در دیتابیس
                Region.objects.update_or_create(
                    name=reg_name,
                    level=config['level'],
                    parent=parent_region,
                    defaults={'geom': geom}
                )
                count += 1

            print(f"✅ تعداد {count} منطقه برای سطح {config['level']} ثبت/بروزرسانی شد.")

        print("\n--- 🚀 تمام لایه‌ها با موفقیت وارد دیتابیس شدند ---")

    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    target_zip = r'C:\Users\Arefkaabi\Downloads\آخرین-تقسیمات-سیاسی-ایران-1400.zip'
    run_multi_layer_import(target_zip)