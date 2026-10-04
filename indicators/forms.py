from django import forms

# نکته: تابع create_dynamic_expert_form قبلی از این فایل حذف شد. آن تابع
# هیچ‌جای پروژه import نمی‌شد (منطق واقعی فرم داینامیک در
# views.submit_expert_answer پیاده‌سازی شده) و به یک فیلد ناموجود
# (VariableDefinition.options) ارجاع می‌داد که هیچ‌وقت در مدل تعریف نشده
# بود؛ یعنی کد مرده‌ای بود که حتی اگر صدا زده می‌شد هم با AttributeError
# می‌ترکید.


class RegionCommentForm(forms.Form):
    """اعتبارسنجی ساده‌ی متن نظر/پاسخ در ترد کامنت‌های سلسله‌مراتبی مناطق."""
    message = forms.CharField(
        label="متن نظر",
        widget=forms.Textarea(attrs={'rows': 3}),
        max_length=2000,
        required=True,
    )
    parent_id = forms.IntegerField(required=False)
    indicator_id = forms.IntegerField(required=False)
    crop_id = forms.IntegerField(required=False)
