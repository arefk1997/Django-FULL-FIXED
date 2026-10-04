"""
accounts/tree_utils.py

پیاده‌سازی مرکزیِ پیمایش درخت parent/sub_* برای مدل‌هایی مثل Region، Company
و Activity که ساختار سلسله‌مراتبی دارند.

قبلاً همین منطق (یافتن یک گره و همه‌ی نوادگانش) سه بار جداگانه نوشته شده بود:
- Region.get_all_subregions_ids  (accounts/models.py)
- IndicatorDefinition._get_subregion_ids  (indicators/models.py)
- _get_company_and_sub_ids  (accounts/views.py، برای مدل Company)

هر سه نسخه‌ی قبلی بازگشتی بودند و به ازای هر گره یک کوئری جداگانه به
دیتابیس می‌زدند (N+1 روی درخت). نسخه‌ی زیر کل جدول را با یک کوئری واحد
می‌خواند (فقط ستون‌های id و parent_id)، نگاشت parent→children را در حافظه
می‌سازد، و از همان‌جا با BFS زیردرخت را استخراج می‌کند. برای درخت‌هایی با چند
هزار رکورد (مثل تقسیمات کشوری) این روش به‌طور محسوسی سریع‌تر است.

برای درخت‌های بسیار بزرگ‌تر (صدها هزار گره) یا پیمایش‌های بسیار پرتکرار، در
نهایت بهتر است از django-treebeard/django-mptt (که این نگاشت را در خود
دیتابیس با یک فیلد path/lft-rght نگه می‌دارند) یا یک CTE بازگشتی در
PostgreSQL استفاده کنید؛ این تابع صرفاً رفع دوباره‌کاری کد و رفع N+1 ساده
است، نه معادل کامل یک کتابخانه‌ی درختی اختصاصی.
"""


def get_subtree_ids(model_cls, root_id, parent_field='parent_id'):
    """
    همه‌ی id های زیردرخت (شامل خود root_id) را برای model_cls برمی‌گرداند.

    model_cls: مدلی با فیلد parent (self-FK)، مثل Region یا Company.
    root_id: شناسه‌ی گره‌ی ریشه.
    parent_field: نام ستون FK والد در دیتابیس (پیش‌فرض 'parent_id').
    """
    rows = model_cls.objects.values_list('id', parent_field)

    children_map = {}
    for node_id, parent_id in rows:
        children_map.setdefault(parent_id, []).append(node_id)

    result = []
    queue = [root_id]
    while queue:
        current_id = queue.pop()
        result.append(current_id)
        queue.extend(children_map.get(current_id, []))

    return result
