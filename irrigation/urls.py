from django.urls import path
from . import views

urlpatterns = [
    path('calendar/', views.irrigation_calendar_view, name='irrigation_calendar'),
    path('record/<int:plan_id>/', views.record_irrigation, name='record_irrigation'),
]
