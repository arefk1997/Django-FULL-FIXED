import numpy as np
from collections import Counter
from django.db.models import Avg, Min, Max, Sum
from .models import Question, Answer, QuestionAnalytics


class QuestionAnalyticsService:
    """لایه سرویس مستقل برای محاسبه شاخص‌های آماری سوالات بر اساس دکترین DDD"""

    @staticmethod
    def calculate_numerical_stats(question_id):
        answers_queryset = Answer.objects.filter(question_id=question_id).values_list('text_answer', flat=True)

        # تبدیل داده‌های متنی به مقادیر معتبر اعشاری
        clean_data = []
        for ans in answers_queryset:
            try:
                clean_data.append(float(ans))
            except ValueError:
                continue

        if not clean_data:
            return {}

        data_array = np.array(clean_data)

        metrics = {
            'mean': float(np.mean(data_array)),
            'min': float(np.min(data_array)),
            'max': float(np.max(data_array)),
            'sum': float(np.sum(data_array)),
            'variance': float(np.var(data_array)),
            'std_dev': float(np.std(data_array)),
            'median': float(np.median(data_array))
        }
        return metrics

    @staticmethod
    def calculate_choice_stats(question_id):
        question = Question.objects.get(id=question_id)
        answers = Answer.objects.filter(question=question).values_list('text_answer', flat=True)
        total_count = answers.count()

        if total_count == 0:
            return {}, 0.0

        choices_list = question.get_choices_dict()
        frequencies = Counter(answers)

        choice_metrics = {}
        total_score = 0.0
        scored_responses_count = 0

        # فرض بر این است که گزینه‌ها می‌توانند با ساختار امتیازدهی مثل (گزینه|امتیاز) ثبت شده باشند یا بر اساس ایندکس وزن‌دهی شوند
        for index, choice_node in enumerate(choices_list, start=1):
            text = choice_node['text']
            count = frequencies[text]
            percentage = round((count / total_count) * 100, 2)

            # استخراج وزن یا مقدار عددی برای محاسبه شاخص رضایت
            weight = index
            if '|' in text:
                try:
                    parts = text.split('|')
                    text = parts[0].strip()
                    weight = float(parts[1].strip())
                except ValueError:
                    pass

            choice_metrics[text] = {
                'count': count,
                'percentage': percentage,
                'weight': weight
            }

            total_score += (count * weight)
            scored_responses_count += count

        # محاسبه شاخص رضایت مشتری/کشاورز (CSI) بر پایه مقیاس درصد استاندارد
        max_possible_weight = len(choices_list)
        if scored_responses_count > 0 and max_possible_weight > 0:
            avg_score = total_score / scored_responses_count
            satisfaction_index = (avg_score / max_possible_weight) * 100
        else:
            satisfaction_index = 0.0

        return choice_metrics, round(satisfaction_index, 2)

    @classmethod
    def run_full_analysis(cls, question_id):
        """متد هماهنگ‌کننده اصلی برای بروزرسانی اتمیک جدول تحلیلی سوال"""
        question = Question.objects.get(id=question_id)
        total_responses = Answer.objects.filter(question=question).count()

        numerical_metrics = {}
        choice_metrics = {}
        satisfaction_index = 0.0

        if question.type == 'number':
            numerical_metrics = cls.calculate_numerical_stats(question_id)
        elif question.type == 'radio':
            choice_metrics, satisfaction_index = cls.calculate_choice_stats(question_id)

        QuestionAnalytics.objects.update_or_create(
            question=question,
            defaults={
                'total_responses': total_responses,
                'numerical_metrics': numerical_metrics,
                'choice_metrics': choice_metrics,
                'satisfaction_index': satisfaction_index,
            }
        )