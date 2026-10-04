# راهنمای نصب و اجرا (نسخه‌ی کامل اصلاح‌شده)

این پوشه، کل پروژه است (نه فقط فایل‌های diff) با تمام اصلاحات اعمال‌شده روی آن.
فهرست کامل تغییرات در پایین همین فایل آمده.

## پیش‌نیازها

- Python 3.11+
- PostgreSQL + پسوند PostGIS
- GDAL/GEOS (روی ویندوز: OSGeo4W، روی لینوکس: `apt install gdal-bin libgdal-dev`)
- Redis (فقط اگر می‌خواهید Celery را هم اجرا کنید؛ بدون آن هم سایت بالا می‌آید،
  فقط تسک‌های تحلیل پرسشنامه async اجرا نمی‌شوند)

## مراحل نصب

```bash
# ۱. محیط مجازی
python -m venv .venv
source .venv/bin/activate   # ویندوز: .venv\Scripts\activate

# ۲. نصب وابستگی‌ها
pip install -r requirements.txt

# ۳. تنظیم متغیرهای محیطی
cp .env.example .env
# فایل .env را باز کنید و مقادیر واقعی (SECRET_KEY جدید، رمز دیتابیس، ایمیل) را پر کنید

# ۴. ساخت دیتابیس (در psql)
# CREATE DATABASE water_management;
# \c water_management
# CREATE EXTENSION postgis;

# ۵. اجرای مهاجرت‌ها
python manage.py migrate

# ۶. ساخت کاربر ادمین
python manage.py createsuperuser

# ۷. اجرا
python manage.py runserver
```

### درباره‌ی مهاجرت‌های جدید (مهم)

دو فایل migration به‌صورت دستی اضافه شده‌اند، چون در محیطی که این اصلاحیه
آماده شد Django/PostGIS/GDAL نصب نبود و امکان اجرای واقعی `makemigrations`
نبود:

- `accounts/migrations/0025_review_fields_and_cleanup.py`
- `indicators/migrations/0012_expertanswersubmission_task.py`

**قبل از اجرای `migrate` روی دیتابیس واقعی:**
1. از دیتابیس بک‌آپ بگیرید.
2. بررسی کنید آیا `national_code` تکراری در جدول `accounts_customuser` دارید
   (کوئری راهنما داخل خود فایل migration کامنت شده است) — چون این migration
   `unique=True` را روی آن اعمال می‌کند.
3. بعد از `migrate`، حتماً یک بار `python manage.py makemigrations --check`
   بزنید تا مطمئن شوید migration state با مدل‌های فعلی ۱۰۰٪ همخوان است. اگر
   Django چیز اضافه‌ای (مثلاً به‌خاطر تفاوت نسخه) تشخیص داد، یک migration
   تکمیلی با `makemigrations` بسازید.

### اجرای Celery (اختیاری)

```bash
redis-server &
celery -A my_proj worker -l info -Q analytics,kpis
```

## فهرست کامل تغییرات نسبت به نسخه‌ی اولیه

### امنیت
- حذف SECRET_KEY و رمز دیتابیس هاردکد شده از `settings.py` → انتقال به `.env`
- `DEBUG`/`ALLOWED_HOSTS` از env خوانده می‌شوند
- تنظیمات امنیتی production (`SECURE_SSL_REDIRECT`, کوکی‌های Secure, HSTS) اضافه شد
- `.gitignore` ساخته شد؛ `.venv`, `.git` قدیمی، `db.sqlite3`، `media/documents`
  (تصاویر مدارک هویتی) و `.idea` از این تحویل حذف شدند
- `eval()` ناامن فرمول شاخص‌ها با یک ارزیاب امن مبتنی بر `ast`
  (`indicators/safe_eval.py`) جایگزین شد
- رفع IDOR در `review_task`, `approve_farmer`, `manage_permissions_view`,
  `assign_sub_task_view` (کنترل مالکیت و قلمرو مدیریتی)
- `@require_POST` روی تمام اکشن‌های تغییردهنده (قبلاً بعضی با GET هم کار می‌کردند)
- حذف نشت متن خطای خام (`str(e)`) به کاربر؛ جایگزینی با `logging.exception`
- تایل نقشه از `http://` به `https://` (رفع mixed content) + هشدار ToS گوگل

### باگ‌های عملکردی که جریان اصلی برنامه را می‌شکستند
- `Farm.save()`: حذف ارجاع به فیلدهای ناموجود `role`/`managed_regions`
- `@allowed_users(allowed_positions=['farmer'])` در `farms/views.py` هیچ‌وقت
  برای کشاورز true نمی‌شد (چون `position` برای کشاورز همیشه None است) →
  دکوراتور اختصاصی جدید `farmer_required`
- مسیر دوبار `accounts/accounts/...` در urls.py
- URL و قالب گمشده‌ی `answer_task_variables_view`
- `accounts/apps.py` و `surveys/apps.py`: سیگنال‌ها اصلاً ثبت نمی‌شدند چون
  `ready()` وجود نداشت (هم ایمیل تایید حساب، هم تسک Celery تحلیل پرسشنامه)
- سیگنال ایمیل تایید حساب: قبلاً با هر لاگین دوباره ایمیل می‌فرستاد؛ حالا فقط
  روی گذار واقعی False→True
- `indicators/models.py`: `variable__code__icontains` (جستجوی زیررشته‌ای
  اشتباه) → تطبیق دقیق
- `surveys/urls.py`: نبود `app_name = 'surveys'` باعث `NoReverseMatch` روی
  `{% url 'surveys:...' %}` می‌شد
- `irrigation/views.py`: محاسبه‌ی نیاز آبی روزانه کش شد (قبلاً صدها بار در
  هر بار بازکردن صفحه صدا زده می‌شد)، حلقه‌ی بدون‌سقف گذشته‌نگر سقف‌دار شد
- `export_answers_excel` که فقط `pass` بود و ۵۰۰ می‌داد، با خروجی اکسل واقعی
  (openpyxl) پیاده‌سازی شد
- قالب‌های گمشده (`irrigation/no_plan.html`,
  `irrigation/templates/irrigation/calendar.html` که در مسیر اشتباه بود،
  `surveys/survey_list.html`, `accounts/.../answer_variables.html`) ساخته/جابه‌جا شدند
- `farms/tests.py`: رفع `role='farmer'` نامعتبر که تست را از کار می‌انداخت

### طراحی و ساختار
- Choiceهای رشته‌ای به `models.TextChoices` تبدیل شدند
- اعتبارسنجی واقعی کد ملی (الگوریتم رقم کنترل) و شماره تلفن (regex)
- `on_delete` برای `ExpertTask.expert` از `CASCADE` به `PROTECT`
- فیلد تکراری `rejection_reason` حذف و با migration داده به `manager_comment` منتقل شد
- فیلدهای جدید `reviewed_by`/`reviewed_at` برای ثبت تاریخچه‌ی تایید/رد
- **رفع تایید گروهی نادرست**: فیلد جدید `ExpertAnswerSubmission.task` اضافه
  شد تا تایید نهایی یک task فقط submission مرتبط با همان task را verify کند
  (نه همه‌ی submissionهای آن کارشناس برای آن محصول)
- پیمایش بازگشتی تکراری درخت (در Region، IndicatorDefinition، و
  `accounts/views.py`) در یک تابع مشترک `accounts/tree_utils.get_subtree_ids`
  یکپارچه شد (با یک کوئری واحد به‌جای N+1)
- `review_task`: تایید والد فقط وقتی انجام می‌شود که همه‌ی زیروظایف تایید شده باشند
- Celery واقعاً راه‌اندازی شد (`my_proj/celery.py` + تنظیمات در `settings.py`)
  چون `surveys/tasks.py` به آن وابسته بود ولی هیچ app ای برایش تعریف نشده بود

## مواردی که عمداً دست‌نخورده ماندند (تصمیم تیمی/محصولی لازم دارند)

- Squash کردن ۲۴ migration قدیمی `accounts` — بعد از اطمینان از پایداری مدل‌ها
  با `python manage.py squashmigrations accounts 0025` انجام دهید
- فشرده‌سازی/بیلد Tailwind (`tailwind.js` حدود ۴۰۰ کیلوبایت) — نیاز به
  Tailwind CLI دارد
- جایگزینی کامل تایل گوگل با یک سرویس نقشه‌ی مجاز (Mapbox/MapTiler/Google
  Maps Platform با API Key) — نیاز به حساب و کلید API است
- `farms/draw_map.html` در هیچ‌جای پروژه استفاده نمی‌شود (فایل یتیم)؛ اگر
  قرار است استفاده شود باید به `farms/urls.py` وصل شود، وگرنه حذفش کنید
