from django.urls import path
from . import views

app_name = 'indicators'

urlpatterns = [
    # ۱. لیست محصولات فعال جهت شروع ارزیابی و ثبت داده (توسط کارشناس)
    path('crops/', views.crop_list, name='crop_list'),

    # ۲. فرم داینامیک ثبت پیش‌نویس داده‌های عددی و پاسخ‌های کارشناسی برای یک محصول خاص
    path('submit/<int:crop_id>/', views.submit_expert_answer, name='submit_expert_answer'),

    # ۳. میز کار و داشبورد محاسباتی مدیر (تحلیل آنی و هوشمند شاخص‌های بهره‌وری آب بر اساس محصول)
    path('summary/', views.manager_indicator_summary, name='manager_indicator_summary'),

    # ۴. گزارشات آماری پیشرفته، نمودارهای میله‌ای و خطی پایش عملکرد کل شهرستان
    path('statistics/', views.indicator_statistics, name='indicator_statistics'),

    # ۵. داده‌ی GeoJSON هیت‌مپ برای drill-down روی نقشه (AJAX)
    path('heatmap-data/', views.indicator_heatmap_data, name='indicator_heatmap_data'),

    # ۶. ترد نظرات مدیریتی سلسله‌مراتبی روی یک منطقه (AJAX)
    path('regions/<int:region_id>/comments/', views.region_comments_view, name='region_comments'),
    path('comments/<int:comment_id>/resolve/', views.resolve_region_comment, name='resolve_region_comment'),

    # ۷. نمای شاخص‌ها برای کشاورز (فقط شاخص‌های visible_to_farmers=True)
    path('farmer/summary/', views.farmer_indicator_view, name='farmer_indicator_summary'),
]