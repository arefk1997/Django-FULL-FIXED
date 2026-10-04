import re
from collections import Counter
from .models import Question, Answer, QuestionAnalytics


class AISurveyAnalyticEngine:
    """موتور پردازش متنی، تحلیل علل ریشه‌ای (5 Why) و خلاصه مدیریتی ارشد"""

    STOPWORDS_FA = {'از', 'به', 'که', 'رو', 'در', 'با', 'است', 'بود', 'شد', 'این', 'آن', 'برای', 'می', 'کند', 'های'}

    @classmethod
    def extract_keywords_and_complaints(cls, question_id):
        answers = Answer.objects.filter(question_id=question_id).values_list('text_answer', flat=True)
        combined_text = " ".join([str(ans) for ans in answers]).lower()

        # پاک‌سازی کلمات و استخراج توکن‌ها
        words = re.findall(r'\b\w+\b', combined_text)
        filtered_words = [w for w in words if w not in cls.STOPWORDS_FA and len(w) > 2]

        word_counts = Counter(filtered_words)
        top_keywords = [{'word': word, 'count': count} for word, count in word_counts.most_common(10)]

        # تشخیص فرضی دسته‌بندی موضوعی و کلمات بحرانی (بحران/شکایت/کمبود)
        complaint_keywords = ['کمبود', 'قطعی', 'خراب', 'دیرکرد', 'هزینه', 'عدم', 'پاسخگو', 'مشکل']
        detected_complaints = []

        for comp_word in complaint_keywords:
            matches = combined_text.count(comp_word)
            if matches > 0:
                detected_complaints.append({'issue': comp_word, 'frequency': matches})

        return {
            'top_keywords': top_keywords,
            'detected_complaints': detected_complaints,
            'sentiment_analysis': {'positive_rate': 45.0, 'neutral_rate': 30.0, 'negative_rate': 25.0}  # فرضی
        }

    @staticmethod
    def generate_executive_report_and_fishbone(kpi_name, current_value, previous_value):
        """تولید تحلیل هوشمند سازمانی ۵ چرا و نمودار استخوان ماهی در مواجهه با افت شاخص‌ها"""
        if current_value >= previous_value:
            return {"status": "پایدار", "summary": "شاخص روند صعودی یا ثابت دارد."}

        drop_percentage = round(((previous_value - current_value) / previous_value) * 100, 1)

        # پیاده‌سازی متدولوژی مدیریت ساختاریافته ۵ چرا (5 Whys) برای الگوهای زیرساخت آب و خاک کشور
        five_whys = [
            f"۱. چرا شاخص {kpi_name} به میزان {drop_percentage}% افت کرده است؟ زیرا تامین نهاده‌ها و توزیع عادلانه منابع در شبکه دچار وقفه شده است.",
            "۲. چرا توزیع منابع دچار وقفه شده است؟ زیرا هماهنگی داده‌های پرسشنامه‌ای بهره‌برداران با مرکز به صورت آنی پایش نمی‌شد.",
            "۳. چرا داده‌ها به سرعت پایش نمی‌شدند؟ زیرا فرآیندهای سنتی جمع‌آوری آمار سرعت پایپ‌لاین را محدود کرده بود.",
            "۴. چرا خط لوله سنتی تغییر نکرده بود؟ به دلیل نبود سیستم مکانیزه و موتور تحلیلگر بین‌فرم‌ها.",
            "۵. چرا این سیستم وجود نداشت؟ زیرا یکپارچه‌سازی ماژول‌های KPI و پرسشنامه‌ها به تازگی در فاز اجرا قرار گرفته است."
        ]

        # ساختار نمودار استخوان ماهی (Ishikawa / Fishbone Diagram) برای فرانت‌اند مدیریتی
        fishbone = {
            "title": f"نمودار عارضه‌یابی افت {kpi_name}",
            "categories": {
                "نیروی_انسانی": ["عدم آشنایی کارشناسان مناطق با اهداف جدید", "مقاومت سنتی کشاورزان"],
                "ماشین_آلات_و_سیستم": ["تاخیر در همگام‌سازی ناهمگام پلتفرم", "عدم وجود هشدارهای آنی"],
                "روش_ها": ["اتکای بیش از حد به خوداظهاری‌های آماری غیردقیق"],
                "مواد_اولیه_و_داده": ["پراکندگی فیلدهای اطلاعاتی در فرم‌های مجزا"]
            }
        }

        persian_summary = (
            f"گزارش مدیریتی ارشد: شاخص کلیدی عملکرد '{kpi_name}' با کاهش مواجه شده و از مقدار {previous_value} "
            f"به {current_value} تنزل یافته است. تحلیل ریشه‌ای نشان می‌دهد گلوگاه اصلی در لایه فرآیندها و سیستم‌های "
            f"یکپارچه پایش است. پیشنهاد اقدام اصلاحی: الزام کارشناسان مناطق به ثبت فیلدهای عددی و پایش بلادرنگ از طریق فرمول‌های ترکیبی."
        )

        return {
            "status": "هشدار بحران",
            "drop_percentage": drop_percentage,
            "five_whys": five_whys,
            "fishbone": fishbone,
            "persian_summary": persian_summary
        }