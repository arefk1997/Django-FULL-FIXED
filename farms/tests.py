"""
farms/tests.py

تغییرات:
- create_user(..., role='farmer') حذف شد؛ CustomUser فیلد role ندارد
  (user_type='farmer' فیلد درست است) و این خط با TypeError کرش می‌کرد.
- assertEqual روی __str__ با خروجی واقعی Farm.__str__ (که
  f"{name} ({farmer.username})" است، نه متنی با "مالک:" و "هکتار") هماهنگ شد.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon
from .models import Farm

User = get_user_model()


class FarmModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testfarmer',
            password='password123',
            user_type='farmer',
        )

        self.square_poly = Polygon((
            (51.000, 35.000),
            (51.001, 35.000),
            (51.001, 35.001),
            (51.000, 35.001),
            (51.000, 35.000),
        ))

    def test_farm_creation_and_area_calculation(self):
        """تست ایجاد مزرعه و بررسی محاسبه خودکار مساحت."""
        farm = Farm.objects.create(
            farmer=self.user,
            name="مزرعه نمونه",
            boundary=self.square_poly,
        )

        self.assertEqual(farm.name, "مزرعه نمونه")
        self.assertEqual(farm.farmer.username, "testfarmer")
        self.assertIsNotNone(farm.area_hectares)
        self.assertTrue(farm.area_hectares > 0)

    def test_farm_str_method(self):
        """تست خروجی متنی مدل - باید دقیقاً با Farm.__str__ واقعی مطابقت داشته باشد."""
        farm = Farm.objects.create(
            farmer=self.user,
            name="مزرعه گندم",
            boundary=self.square_poly,
        )
        expected_str = f"مزرعه گندم ({self.user.username})"
        self.assertEqual(str(farm), expected_str)
