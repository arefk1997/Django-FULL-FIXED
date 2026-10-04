from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('surveys/', include('surveys.urls')),
    path('chaining/', include('smart_selects.urls')),
    path('irrigation/', include('irrigation.urls')),
    path('farms/', include('farms.urls', namespace='farms')),
    path('indicators/', include('indicators.urls')),

    # صفحه اصلی پروژه
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]

# اضافه کردن مسیر فایل‌های رسانه‌ای (تصاویر و اسناد)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)