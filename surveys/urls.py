from django.urls import path
from . import views

# اضافه شد: بدون app_name، فراخوانی‌های {% url 'surveys:survey_list' %} یا
# redirect('surveys:survey_list') در کد (و در قالب‌ها) با NoReverseMatch
# شکست می‌خورند، چون این urls.py با include('surveys.urls') بدون namespace
# در my_proj/urls.py اضافه شده بود.
app_name = 'surveys'

urlpatterns = [
    # نمایش لیست تمام پرسشنامه‌ها (اختیاری)
    path('', views.survey_list, name='survey_list'),

    # ثبت یک پرسشنامه خاص با استفاده از ID
    path('submit/<int:survey_id>/', views.submit_survey, name='submit_survey'),

    # گزارش پاسخ‌های کاربر
    path('report/', views.survey_report, name='survey_report'),

    # خروجی اکسل
    path('report/export/', views.export_answers_excel, name='export_excel'),
]