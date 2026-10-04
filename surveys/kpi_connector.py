from django.apps import apps
from .models import SurveyKPIBinding, QuestionAnalytics


class KPIMappingService:
    """موتور پویای همگام‌سازی خروجی‌های پرسشنامه با لایه شاخص‌های کلیدی عملکرد (KPI)"""

    @staticmethod
    def sync_binding_to_kpi(binding_id):
        try:
            binding = SurveyKPIBinding.objects.get(id=binding_id, is_active=True)
            new_value = 0.0

            if binding.binding_type == 'question_csi' and binding.source_question:
                analytics = QuestionAnalytics.objects.get(question=binding.source_question)
                new_value = analytics.satisfaction_index

            elif binding.binding_type == 'question_mean' and binding.source_question:
                analytics = QuestionAnalytics.objects.get(question=binding.source_question)
                new_value = analytics.numerical_metrics.get('mean', 0.0)

            elif binding.binding_type == 'formula_output' and binding.source_formula:
                # فراخوانی از مدل محاسباتی ترکیبی که قبلاً توسعه داده بودیم
                # پیدا کردن آخرین نتیجه برای تست ساختار کلان
                CalculatedResult = apps.get_model('surveys', 'CalculatedResult')
                latest_res = CalculatedResult.objects.filter(formula=binding.source_formula).order_by(
                    '-calculated_at').first()
                if latest_res:
                    new_value = latest_res.calculated_value

            # تزریق مقدار محاسبه شده به فیلدهای مدل VariableDefinition در اپلیکیشن indicators
            target_var = binding.target_variable

            # این بخش فرض می‌کند مدل مقصد شما فیلدی برای نگهداری یا لاگ آخرین مقدار دارد
            if hasattr(target_var, 'current_value'):
                target_var.current_value = new_value
                target_var.save()

            return True
        except Exception:
            return False