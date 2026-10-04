from rest_framework import serializers
from .models import Question, QuestionAnalytics

class QuestionAnalyticsSerializer(serializers.ModelSerializer):
    chart_js_config = serializers.SerializerMethodField()
    echarts_config = serializers.SerializerMethodField()

    class Meta:
        model = QuestionAnalytics
        fields = ['total_responses', 'satisfaction_index', 'numerical_metrics', 'choice_metrics', 'text_metrics', 'chart_js_config', 'echarts_config']

    def get_chart_js_config(self, obj):
        """تولید ساختار دیتای کامپوننت‌های Chart.js"""
        if obj.question.type == 'radio':
            labels = list(obj.choice_metrics.keys())
            data = [node['count'] for node in obj.choice_metrics.values()]
            return {
                'type': 'doughnut',
                'data': {
                    'labels': labels,
                    'datasets': [{'label': 'فراوانی گزینه‌ها', 'data': data, 'backgroundColor': ['#10b981', '#f59e0b', '#3b82f6', '#ef4444']}]
                }
            }
        elif obj.question.type == 'number':
            return {
                'type': 'bar',
                'data': {
                    'labels': ['حداقل', 'میانگین', 'میانه', 'حداکثر'],
                    'datasets': [{'label': 'شاخص‌های توصیفی', 'data': [
                        obj.numerical_metrics.get('min', 0),
                        obj.numerical_metrics.get('mean', 0),
                        obj.numerical_metrics.get('median', 0),
                        obj.numerical_metrics.get('max', 0)
                    ], 'backgroundColor': '#3b82f6'}]
                }
            }
        return {}

    def get_echarts_config(self, obj):
        """تولید ساختار آپشن‌های قدرتمند Apache ECharts"""
        if obj.question.type == 'radio':
            return {
                'tooltip': {'trigger': 'item'},
                'series': [{
                    'name': 'توزیع پاسخ‌ها',
                    'type': 'pie',
                    'radius': '50%',
                    'data': [{'value': n['count'], 'name': k} for k, n in obj.choice_metrics.items()]
                }]
            }
        return {}