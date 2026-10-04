import requests
import logging

# تنظیم لاگر برای ثبت خطاهای شبکه بدون متوقف کردن برنامه
logger = logging.getLogger(__name__)


class WeatherService:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    @staticmethod
    def get_evapotranspiration(lat, lon):
        """
        دریافت میزان تبخیر و تعرق روزانه (ET0) بر اساس استاندارد FAO-56
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "et0_fao_evapotranspiration",
            "timezone": "auto",
            "forecast_days": 1
        }

        try:
            # زمان انتظار 5 ثانیه برای جلوگیری از معطل شدن سرور خودمان
            response = requests.get(WeatherService.BASE_URL, params=params, timeout=5)
            response.raise_for_status()  # بررسی اینکه آیا درخواست موفق بوده (200)

            data = response.json()
            et0 = data.get('daily', {}).get('et0_fao_evapotranspiration', [None])[0]
            return et0
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error(f"Weather API Error (ET0): {e}")
            return None

    @staticmethod
    def get_daily_rain(lat, lon):
        """
        دریافت میزان مجموع بارش روز جاری
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum",
            "timezone": "auto",
            "forecast_days": 1
        }

        try:
            response = requests.get(WeatherService.BASE_URL, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            rain = data.get('daily', {}).get('precipitation_sum', [0])[0]
            return rain
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error(f"Weather API Error (Rain): {e}")
            return 0  # در صورت خطا فرض می‌کنیم بارانی نمی‌بارد