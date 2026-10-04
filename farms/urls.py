from django.urls import path
from . import views

app_name = 'farms'

urlpatterns = [
    # ۱. ثبت مزرعه جدید (صفحه نقشه و فرم مشخصات)
    path('add/', views.add_farm_view, name='add_farm'),

    # ۲. مشاهده لیست مزارع کشاورز
    path('list/', views.farm_list_view, name='farm_list'),

    # ۳. گزارش سلامت ماهواره‌ای و جزئیات پایش (NDVI و رطوبت)
    path('health/<int:farm_id>/', views.farm_health_detail, name='farm_health'),
]