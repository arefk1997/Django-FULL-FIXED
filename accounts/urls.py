# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- فرآیندهای احرز هویت و عضویت ---
    path('signup/', views.farmer_signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- پیشخوان مرکزی و مسیریاب هوشمند لایه‌ها ---
    path('dashboard/', views.dashboard_router, name='dashboard'),
    path('dashboard/official/', views.official_dashboard, name='official_dashboard'),
    path('dashboard/farmer/', views.farmer_dashboard, name='farmer_dashboard'),
    path('dashboard/manage-permissions/', views.manage_permissions_view, name='manage_permissions'),

    # --- مدیریت داده‌های جغرافیایی حوزه‌ای (AJAX) ---
    path('ajax/load-sub-regions/', views.ajax_load_sub_regions, name='ajax_load_sub_regions'),

    # --- فرآیندهای مدیریتی و نظارتی (Security Actions) ---
    path('approve-farmer/<int:farmer_id>/', views.approve_farmer, name='approve_farmer'),
    path('review-task/<int:task_id>/', views.review_task, name='review_task'),

    # نکته: قبلاً این مسیر 'accounts/tasks/<id>/assign/' بود. چون این فایل
    # با include('accounts.urls') و پیشوند 'accounts/' در my_proj/urls.py
    # اضافه می‌شود، آدرس نهایی به‌اشتباه '/accounts/accounts/tasks/.../assign/'
    # می‌شد. پیشوند تکراری حذف شد.
    path('tasks/<int:task_id>/assign/', views.assign_sub_task_view, name='assign_sub_task'),
    path('tasks/revoke/<int:task_id>/', views.revoke_assigned_task_view, name='revoke_assigned_task'),

    # اضافه شد: این ویو در views.py وجود داشت ولی هیچ URL برایش تعریف نشده
    # بود، پس کارشناس عملیاتی هیچ‌وقت به فرم پاسخ نمی‌رسید و کل جریان کار در
    # همین نقطه قطع می‌شد.
    path('tasks/<int:task_id>/answer/', views.answer_task_variables_view, name='answer_task_variables'),
]
