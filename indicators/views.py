import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Region

from .forms import RegionCommentForm
from .models import (
    Crop, CropCategory, CropFamily, CropVariety, ExpertAnswerDetail,
    ExpertAnswerSubmission, IndicatorDefinition, RegionIndicatorComment,
    VariableDefinition,
)

# سمت‌هایی که اجازه دارند مستقیماً داده‌ی عددی ثبت کنند (کسانی که واقعاً در
# میدان داده جمع‌آوری می‌کنند). قبلاً این ویو فقط user_type=='official' را
# چک می‌کرد، یعنی حتی یک 'head' هم می‌توانست مستقیم فرم ثبت داده را پر کند؛
# منطقاً این کار باید محدود به کارشناسان (expert/staff) باشد.
DATA_ENTRY_POSITIONS = ['expert', 'staff']


# ==========================================
# ۱. ثبت داده‌های کارشناسی
# ==========================================
@login_required
def submit_expert_answer(request, crop_id):
    """ثبت پاسخ کارشناس با فرم پویا بر اساس متغیرهای فعال محصول و متصل به چارت سازمانی"""
    user = request.user

    if user.user_type != 'official' or user.position not in DATA_ENTRY_POSITIONS:
        messages.error(request, "شما سطح دسترسی لازم برای ثبت داده‌های تخصصی کارشناسی را ندارید.")
        return redirect('dashboard')

    crop = get_object_or_404(Crop, id=crop_id, is_active=True)
    variables = VariableDefinition.objects.filter(crop=crop, is_obsolete=False)

    target_region = user.managed_region
    if not target_region:
        messages.error(request, "خطا: قلمرو جغرافیایی و منطقه مدیریت شما در سیستم تعریف نشده است.")
        return redirect('official_dashboard')

    # ایجاد فرم داینامیک: همه‌ی متغیرها عددی هستند (ExpertAnswerDetail.value
    # یک DecimalField خالص است؛ قبلاً field_type روی VariableDefinition
    # امکان انتخاب 'text' را هم می‌داد که عملاً با مدل ناسازگار بود و منجر
    # به خطا در ذخیره می‌شد).
    fields = {}

    varieties = CropVariety.objects.filter(crop=crop)
    if varieties.exists():
        fields['variety'] = forms.ModelChoiceField(
            queryset=varieties,
            label="رقم محصول",
            required=False,
            empty_label="انتخاب رقم محصول (اختیاری)..."
        )

    for var in variables:
        fields[f'var_{var.id}'] = forms.DecimalField(
            label=var.name,
            required=True,
            max_digits=15,
            decimal_places=3,
        )

    DynamicForm = type('DynamicExpertForm', (forms.Form,), fields)

    if request.method == 'POST':
        form = DynamicForm(request.POST)
        if form.is_valid():
            selected_variety = form.cleaned_data.get('variety', None) if 'variety' in form.cleaned_data else None

            submission = ExpertAnswerSubmission.objects.create(
                company=user.company,
                region=target_region,
                crop=crop,
                variety=selected_variety,
                expert=user,
                status='draft'
            )

            for key, value in form.cleaned_data.items():
                if key == 'variety':
                    continue
                var_id = key.split('_')[1]
                ExpertAnswerDetail.objects.create(
                    submission=submission,
                    variable_id=var_id,
                    value=value
                )

            messages.success(request,
                             f"پیش‌نویس داده‌های محصول {crop.name} با موفقیت ایجاد شد. جهت اعمال در محاسبات، تسک مربوطه را ارسال کنید.")
            return redirect('indicators:crop_list')
    else:
        form = DynamicForm()

    for name, field in form.fields.items():
        field.widget.attrs.update({
            'class': 'w-full px-5 py-4 border-2 border-gray-100 rounded-2xl focus:ring-4 focus:ring-emerald-500/10 focus:border-emerald-500 outline-none transition-all mb-4 text-slate-800 font-bold',
            'placeholder': f'وارد کردن {field.label}...'
        })

    return render(request, 'indicators/submit_form.html', {
        'form': form,
        'crop': crop,
        'variables_count': variables.count(),
        'region': target_region
    })


@login_required
def crop_list(request):
    """لیست محصولات فعال برای شروع فرآیند ثبت داده"""
    if request.user.user_type != 'official' or request.user.position not in DATA_ENTRY_POSITIONS:
        return redirect('dashboard')
    crops = Crop.objects.filter(is_active=True).select_related('category')
    return render(request, 'indicators/crop_list.html', {'crops': crops})


# ==========================================
# ۲. داشبورد مقایسه/درختی شاخص‌ها برای پرسنل اداری (drill-down + heatmap)
# ==========================================
def _region_breadcrumb(region):
    """زنجیره‌ی منطقه از ریشه تا خود region، برای نمایش مسیر drill-down."""
    chain = []
    current = region
    while current:
        chain.append(current)
        current = current.parent
    return list(reversed(chain))


def _resolve_scope_root(user):
    """سقف دسترسی جغرافیایی کاربر؛ بدون منطقه‌ی مدیریتی مشخص (مثلاً superuser ستادی)، None یعنی کل کشور."""
    return user.managed_region


def _user_can_access_region(user, region):
    """آیا region داخل قلمرو مدیریتی کاربر هست؟ (خودش یا هر زیرمجموعه‌ای از آن)."""
    root = _resolve_scope_root(user)
    if root is None:
        return True  # کاربری بدون managed_region محدود (مثلاً superuser) در این پیاده‌سازی دسترسی کامل دارد
    return region.id in root.get_all_subregions_ids()


@login_required
def manager_indicator_summary(request):
    """
    میز کار تحلیلی شاخص‌های بهره‌وری برای پرسنل اداری: انتخاب منطقه (با
    drill-down/drill-up روی چارت مناطق)، فیلتر محصول/دسته/خانواده، و
    مقایسه‌ی چند شاخص هم‌زمان. برای کشاورزان این صفحه کاملاً بسته است؛
    کشاورز فقط farmer_indicator_view را می‌بیند.
    """
    user = request.user
    if user.user_type != 'official':
        return redirect('dashboard')

    root = _resolve_scope_root(user)

    region_id = request.GET.get('region')
    if region_id:
        selected_region = get_object_or_404(Region, id=region_id)
        if not _user_can_access_region(user, selected_region):
            messages.error(request, "این منطقه خارج از قلمرو مدیریتی شماست.")
            selected_region = root
    else:
        selected_region = root

    children_regions = Region.objects.filter(parent=selected_region).order_by('name') if selected_region else \
        Region.objects.filter(level=1).order_by('name')

    # شاخص‌هایی که در سطح منطقه‌ی انتخاب‌شده معنی دارند
    all_indicators = IndicatorDefinition.objects.all().select_related('target_category', 'target_family')
    if selected_region:
        available_indicators = [i for i in all_indicators if i.is_available_for_level(selected_region.level)]
    else:
        available_indicators = list(all_indicators)

    selected_indicator_ids = [int(i) for i in request.GET.getlist('indicator') if i.isdigit()]
    crop_filter_id = request.GET.get('crop') or None
    category_filter_id = request.GET.get('category') or None
    family_filter_id = request.GET.get('family') or None

    crop_filter = Crop.objects.filter(id=crop_filter_id).first() if crop_filter_id else None
    family_filter = CropFamily.objects.filter(id=family_filter_id).first() if family_filter_id else None

    comparison_rows = []
    for indicator in available_indicators:
        if selected_indicator_ids and indicator.id not in selected_indicator_ids:
            continue

        value, status_message = indicator.calculate_smart(
            region=selected_region, crop=crop_filter, family=family_filter,
        )
        row = {
            'indicator': indicator,
            'value': value,
            'status': status_message,
            'is_valid': value is not None,
        }

        if indicator.breakdown_by_family or indicator.breakdown_by_crop or indicator.breakdown_by_variety:
            row['breakdown'] = indicator.calculate_breakdown(region=selected_region)[1:]  # ردیف اول = کل، همان row['value']

        comparison_rows.append(row)

    context = {
        'selected_region': selected_region,
        'breadcrumb': _region_breadcrumb(selected_region) if selected_region else [],
        'children_regions': children_regions,
        'available_indicators': available_indicators,
        'selected_indicator_ids': selected_indicator_ids,
        'comparison_rows': comparison_rows,
        'categories': CropCategory.objects.all(),
        'families': CropFamily.objects.all(),
        'crops': Crop.objects.filter(is_active=True),
        'crop_filter_id': int(crop_filter_id) if crop_filter_id else None,
        'category_filter_id': int(category_filter_id) if category_filter_id else None,
        'family_filter_id': int(family_filter_id) if family_filter_id else None,
    }
    return render(request, 'indicators/manager_summary.html', context)


@login_required
def indicator_heatmap_data(request):
    """
    داده‌ی GeoJSON برای نمایش هیت‌مپ + drill-down: مقدار یک شاخص مشخص را
    برای هر یک از زیرمنطقه‌های مستقیمِ منطقه‌ی داده‌شده محاسبه و برمی‌گرداند.
    """
    user = request.user
    if user.user_type != 'official':
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)

    # اصلاح شد: قبلاً indicator_id الزامی بود و بدون آن کل درخواست با خطای
    # ۴۰۰ رد می‌شد. یعنی تا وقتی حتی یک IndicatorDefinition در دیتابیس
    # تعریف نشده بود (یا کاربر هنوز شاخصی انتخاب نکرده بود)، نقشه اصلاً هیچ
    # مرزی نمی‌گرفت تا رسم کند. حالا indicator اختیاری است: اگر نبود، فقط
    # مرزهای مناطق را با مقدار ۰ برمی‌گردانیم تا نقشه همیشه قابل مشاهده باشد.
    indicator_id = request.GET.get('indicator_id')
    indicator = get_object_or_404(IndicatorDefinition, id=indicator_id) if indicator_id else None

    region_id = request.GET.get('region_id')
    if region_id:
        parent_region = get_object_or_404(Region, id=region_id)
        if not _user_can_access_region(user, parent_region):
            return JsonResponse({'error': 'این منطقه خارج از قلمرو مدیریتی شماست.'}, status=403)
        children = Region.objects.filter(parent=parent_region)
    else:
        root = _resolve_scope_root(user)
        if root:
            children = Region.objects.filter(parent=root)
            parent_region = root
        else:
            children = Region.objects.filter(level=1)
            parent_region = None

    crop_filter_id = request.GET.get('crop_id')
    crop_filter = Crop.objects.filter(id=crop_filter_id).first() if crop_filter_id else None

    features = []
    for region in children:
        if indicator is not None:
            raw_value, status = indicator.calculate_smart(region=region, crop=crop_filter)
        else:
            raw_value, status = None, "شاخصی برای نمایش انتخاب نشده است."

        # اصلاح شد: قبلاً وقتی calculate_smart مقدار None برمی‌گرداند (چون
        # هنوز داده‌ای برای آن منطقه ثبت نشده)، همان None مستقیم به
        # فرانت‌اند می‌رفت. جاوااسکریپت هم این را به رنگ خاکستری نشان
        # می‌داد که مشکلی نداشت، ولی چون اصلاً این endpoint صدا زده نمی‌شد
        # (به‌خاطر گیت‌های سمت جاوااسکریپت که جداگانه اصلاح شدند)، هیچ‌وقت
        # این حالت دیده نمی‌شد. حالا هم مرز همیشه برمی‌گردد، هم value وقتی
        # داده‌ای نیست به‌جای null عدد صریح ۰ است (طبق درخواست شما)، و
        # has_data جدا مشخص می‌کند که آیا این ۰ واقعی است یا فقط placeholder
        # برای «داده نداریم» - تا مقیاس رنگی هیت‌مپ با صفرهای ساختگی خراب
        # نشود (وگرنه یک منطقه با داده‌ی واقعی ۵۰ در کنار ده‌ها منطقه‌ی
        # «بدون داده» که انگار همه ۰ هستند، رنگ‌بندی را کاملاً به‌هم می‌ریزد).
        has_data = raw_value is not None
        value = raw_value if has_data else 0

        geometry = json.loads(region.geom.geojson) if region.geom else None
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {
                'id': region.id,
                'name': region.name,
                'level': region.level,
                'value': value,
                'has_data': has_data,
                'status': status,
                'has_children': region.sub_regions.exists(),
            }
        })

    return JsonResponse({
        'type': 'FeatureCollection',
        'parent': {'id': parent_region.id, 'name': parent_region.name} if parent_region else None,
        'features': features,
    })


# ==========================================
# ۳. نظرات مدیریتی سلسله‌مراتبی روی مناطق
# ==========================================
@login_required
def region_comments_view(request, region_id):
    """
    GET: فهرست تردِ نظرات روی یک منطقه (برای نمایش در پنل کناری نقشه).
    POST: ثبت نظر/پاسخ جدید.

    دسترسی: فقط کاربرانی که منطقه داخل قلمرو مدیریتی‌شان است (خودشان یا
    بالادستشان) می‌توانند نظر ثبت/مشاهده کنند؛ یعنی هم مدیر بالادست
    می‌تواند برای زیرمجموعه کامنت بگذارد، هم مسئول همان منطقه می‌تواند
    پاسخ بدهد.
    """
    region = get_object_or_404(Region, id=region_id)
    user = request.user

    if user.user_type != 'official':
        raise Http404()

    is_upstream = _user_can_access_region(user, region)
    is_local_official = (user.managed_region_id == region.id)
    if not (is_upstream or is_local_official):
        return JsonResponse({'error': 'شما دسترسی ثبت/مشاهده‌ی نظر برای این منطقه را ندارید.'}, status=403)

    if request.method == 'POST':
        form = RegionCommentForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': 'متن نظر نامعتبر یا خالی است.'}, status=400)

        parent_comment = None
        if form.cleaned_data['parent_id']:
            parent_comment = get_object_or_404(
                RegionIndicatorComment, id=form.cleaned_data['parent_id'], region=region
            )

        RegionIndicatorComment.objects.create(
            region=region,
            indicator_id=form.cleaned_data['indicator_id'],
            crop_id=form.cleaned_data['crop_id'],
            author=user,
            parent=parent_comment,
            message=form.cleaned_data['message'].strip(),
        )

    threads = RegionIndicatorComment.objects.filter(region=region, parent__isnull=True) \
        .select_related('author').prefetch_related('replies__author').order_by('-created_at')

    def serialize(comment):
        return {
            'id': comment.id,
            'author': comment.author.get_full_name() if comment.author and comment.author.get_full_name() else getattr(comment.author, 'username', '—'),
            'message': comment.message,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_resolved': comment.is_resolved,
            'replies': [serialize(r) for r in comment.replies.all().order_by('created_at')],
        }

    return JsonResponse({
        'region': {'id': region.id, 'name': region.name},
        'can_reply': True,
        'threads': [serialize(t) for t in threads],
    })


@login_required
@require_POST
def resolve_region_comment(request, comment_id):
    """علامت‌گذاری یک ترد به‌عنوان رسیدگی‌شده، فقط توسط کسی که به آن منطقه دسترسی بالادستی دارد."""
    comment = get_object_or_404(RegionIndicatorComment, id=comment_id)
    if not _user_can_access_region(request.user, comment.region):
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)
    comment.is_resolved = True
    comment.save(update_fields=['is_resolved'])
    return JsonResponse({'status': 'ok'})


# ==========================================
# ۴. گزارشات آماری (داده‌ی واقعی به‌جای مقادیر ساختگی قبلی)
# ==========================================
@login_required
def indicator_statistics(request):
    """صفحه گزارشات آماری: روند ماهانه‌ی ثبت پاسخ‌ها و وضعیت تایید، بر اساس داده‌ی واقعی دیتابیس."""
    if request.user.user_type != 'official':
        return redirect('dashboard')

    from django.db.models import Count
    from django.db.models.functions import TruncMonth

    user = request.user
    root = _resolve_scope_root(user)
    submissions = ExpertAnswerSubmission.objects.all()
    if root:
        submissions = submissions.filter(region_id__in=root.get_all_subregions_ids())

    status_counts = dict(submissions.values_list('status').annotate(c=Count('id')).order_by())

    monthly = (
        submissions.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    trend_labels = [row['month'].strftime('%Y-%m') for row in monthly if row['month']]
    trend_values = [row['count'] for row in monthly if row['month']]

    crop_counts = (
        submissions.values('crop__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    crop_labels = [row['crop__name'] or 'نامشخص' for row in crop_counts]
    crop_values = [row['count'] for row in crop_counts]

    context = {
        'total_submissions': submissions.count(),
        'verified_count': status_counts.get('verified', 0),
        'draft_count': status_counts.get('draft', 0),
        'submitted_count': status_counts.get('submitted', 0),
        'trend_labels_json': json.dumps(trend_labels),
        'trend_values_json': json.dumps(trend_values),
        'crop_labels_json': json.dumps(crop_labels),
        'crop_values_json': json.dumps(crop_values),
    }
    return render(request, 'indicators/statistics.html', context)


# ==========================================
# ۵. نمای شاخص‌ها برای کشاورز (فقط شاخص‌های صراحتاً نمایش‌داده‌شده به کشاورزان)
# ==========================================
@login_required
def farmer_indicator_view(request):
    """
    کشاورز به‌صورت پیش‌فرض به هیچ شاخصی دسترسی ندارد. این ویو فقط
    IndicatorDefinition هایی را نشان می‌دهد که ادمین صراحتاً
    visible_to_farmers=True کرده باشد، و محاسبه هم محدود به منطقه‌ی خودِ
    کشاورز (chosen_region) است.
    """
    user = request.user
    if user.user_type != 'farmer':
        return redirect('dashboard')
    if not user.is_approved:
        return redirect('dashboard')

    region = user.chosen_region
    indicators = IndicatorDefinition.objects.filter(visible_to_farmers=True)

    results = []
    for indicator in indicators:
        if region and not indicator.is_available_for_level(region.level):
            continue
        value, status = indicator.calculate_smart(region=region)
        results.append({'indicator': indicator, 'value': value, 'status': status})

    return render(request, 'indicators/farmer_summary.html', {
        'region': region,
        'results': results,
    })