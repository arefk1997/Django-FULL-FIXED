from django import forms
from .models import VariableDefinition


def create_dynamic_expert_form(crop_instance):
    """ایجاد داینامیک فرم بر اساس متغیرهای تعریف شده برای هر محصول"""
    fields = {}
    variables = VariableDefinition.objects.filter(crop=crop_instance)

    for var in variables:
        if var.field_type == 'number':
            fields[f'var_{var.id}'] = forms.FloatField(label=var.name, required=True)
        elif var.field_type == 'select':
            # تبدیل گزینه‌های وارد شده در ادمین به یک لیست (Tuple)
            choices = [(opt.strip(), opt.strip()) for opt in var.options.split(',')]
            fields[f'var_{var.id}'] = forms.ChoiceField(label=var.name, choices=choices, required=True)
        else:
            fields[f'var_{var.id}'] = forms.CharField(label=var.name, required=True)

    return type('DynamicExpertForm', (forms.Form,), fields)