"""
accounts/decorators.py

تغییرات:
- functools.wraps اضافه شد (بدون آن، نام/داکیومنت ویو زیر دکوراتور گم می‌شد و
  با ابزارهایی مثل django-debug-toolbar یا admin کار درست پیش نمی‌رفت).
- آرگومان پیش‌فرض mutable (`allowed_positions=[]`) به تاپل غیرقابل‌تغییر تبدیل شد.
- مسیر '/accounts/dashboard/' سخت‌کد به reverse('dashboard') تبدیل شد.
"""
from functools import wraps
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def allowed_users(allowed_positions=(), required_level=None):
    """
    ۱. چک کردن سمت اداری (Position) - مثلا head یا group_leader
    ۲. چک کردن سطح عملیاتی (office_level) - مثلا national یا province
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper_func(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            user_position = request.user.position
            position_allowed = user_position in allowed_positions or request.user.is_superuser

            level_allowed = True
            if required_level:
                level_allowed = request.user.office_level == required_level

            if position_allowed and level_allowed:
                return view_func(request, *args, **kwargs)

            position_display = request.user.get_position_display() or "بدون سمت تعریف‌شده"
            dashboard_url = reverse('dashboard')
            forbidden_html = f"""
            <div dir='rtl' style='font-family:Tahoma; text-align:center; padding:100px; background:#f4f7f6;'>
                <div style='background:white; display:inline-block; padding:40px; border-radius:15px; box-shadow:0 10px 25px rgba(0,0,0,0.1);'>
                    <h2 style='color:#e74c3c;'>🚫 عدم دسترسی مجاز</h2>
                    <p style='color:#34495e;'>سمت کاربری شما ({position_display}) اجازه ورود به این بخش را ندارد.</p>
                    <p style='color:#7f8c8d; font-size:13px;'>سطح عملیاتی مورد نیاز: {required_level if required_level else 'تعریف نشده'}</p>
                    <a href='{dashboard_url}' style='display:inline-block; margin-top:20px; padding:10px 25px; background:#3498db; color:white; text-decoration:none; border-radius:8px;'>بازگشت به پیشخوان</a>
                </div>
            </div>
            """
            return HttpResponse(forbidden_html, status=403)
        return wrapper_func
    return decorator


def farmer_required(view_func):
    """
    دکوراتور جداگانه برای صفحات مخصوص کشاورز.

    چرا لازم بود: CustomUser.save() فیلد position را برای کشاورزان همیشه
    None می‌کند (نگاه کنید به accounts/models.py). قبلاً در farms/views.py از
    allowed_users(allowed_positions=['farmer']) استفاده شده بود که چک می‌کرد
    request.user.position == 'farmer' — این شرط برای هیچ کشاورزی True
    نمی‌شود، پس هیچ کشاورزی (به‌جز superuser) به آن صفحات دسترسی نداشت.
    این دکوراتور به‌جای position، از user_type استفاده می‌کند که فیلد درستی
    برای تشخیص کشاورز از پرسنل اداری است.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.user_type != 'farmer' and not request.user.is_superuser:
            return HttpResponse(
                "<div dir='rtl' style='padding:60px;text-align:center;font-family:Tahoma'>"
                "این بخش فقط برای کشاورزان قابل دسترسی است.</div>",
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return wrapper
