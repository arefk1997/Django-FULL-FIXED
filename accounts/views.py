"""
accounts/views.py

خلاصه‌ی تغییرات نسبت به نسخه‌ی قبلی (همه در کامنت‌های محلی توضیح داده شده‌اند):
1. review_task: چک مالکیت (assigned_by == request.user)، الزام وضعیت 'submitted'،
   require_POST، ثبت reviewed_by/reviewed_at، و تایید والد فقط وقتی که همه‌ی
   زیرتسک‌ها تایید شده باشند (نه با تایید اولین‌شان).
2. approve_farmer: چک can_approve_farmers + چک اینکه کشاورز داخل قلمرو مدیریتی
   کاربر است، require_POST.
3. assign_sub_task_view: اعتبارسنجی sub_activity_id (باید زیرمجموعه‌ی واقعی
   فعالیت والد باشد) و region_ids (باید داخل قلمرو مجاز کارشناس هدف باشد)،
   require_POST، پیام خطای عمومی به‌جای str(e) خام.
4. manage_permissions_view: فیلتر position روی کوئری تغییر دسترسی هم اعمال شد
   تا کسی نتواند به هم‌رده یا مافوق خودش دسترسی بدهد.
5. revoke_assigned_task_view: require_POST، پیام خطای عمومی.
6. login_view: به‌جای authenticate() دوباره، از form.get_user() استفاده شد.
7. answer_task_variables_view: تبدیل به Decimal به‌جای float (چون فیلد
   DecimalField است) و try/except برای ورودی نامعتبر.
8. خطاها با logging.exception ثبت می‌شوند، نه چاپ متن خام به کاربر.
"""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, Http404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from .models import CustomUser, Region, Company, Activity, ExpertTask
from .forms import CustomUserCreationForm
from .tree_utils import get_subtree_ids
from django.contrib.auth.forms import AuthenticationForm

from indicators.models import VariableDefinition, ExpertAnswerSubmission, ExpertAnswerDetail

logger = logging.getLogger(__name__)

POSITION_HIERARCHY = {
    'head': ['head', 'deputy', 'group_leader', 'expert', 'staff'],
    'deputy': ['deputy', 'group_leader', 'expert', 'staff'],
    'group_leader': ['expert', 'staff'],
    'expert': ['staff'],
    'staff': [],
}

IMMEDIATE_SUBORDINATES = {
    'head': ['head', 'deputy'],
    'deputy': ['group_leader'],
    'group_leader': ['expert'],
    'expert': ['staff'],
    'staff': [],
}


# ==========================================
# تابع کمکی استخراج کل چارت سازمانی زیرمجموعه
# ==========================================
def _get_company_and_sub_ids(company):
    """
    اصلاح شد: پیمایش بازگشتیِ قبلی (یک کوئری به ازای هر گره) با تابع مشترک
    get_subtree_ids جایگزین شد تا هم کد تکراری حذف شود، هم یک کوئری واحد
    برای کل درخت زده شود.
    """
    if not company:
        return []
    return get_subtree_ids(Company, company.id)


def _get_activity_and_descendant_ids(activity):
    """اعتبارسنجی: یک زیرفعالیت انتخابی باید واقعاً داخل زیردرخت فعالیت والد باشد."""
    return get_subtree_ids(Activity, activity.id)


# ==========================================
# ۱. بارگذاری پویا و زنجیره‌ای مناطق (Ajax)
# ==========================================
def ajax_load_sub_regions(request):
    parent_id = request.GET.get('parent_id')
    if parent_id:
        sub_regions = Region.objects.filter(parent_id=parent_id).values('id', 'name')
        return JsonResponse(list(sub_regions), safe=False)
    return JsonResponse([], safe=False)


# ==========================================
# ۲. فرآیند احرز هویت و ثبت‌نام کشاورزان
# ==========================================
def farmer_signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "ثبت‌نام شما با موفقیت انجام شد. پس از بررسی و تایید صلاحیت توسط مدیر منطقه، پنل شما فعال می‌شود.",
            )
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            # form.get_user() از قبل کاربر احرازشده را دارد؛ فراخوانی دوباره‌ی
            # authenticate() غیرضروری بود و اگر backendهای احراز متفاوت
            # داشتید می‌توانست رفتار متفاوتی هم بدهد.
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# ==========================================
# ۳. روت مسیریابی مرکزی پیشخوان (Router)
# ==========================================
@login_required
def dashboard_router(request):
    user = request.user
    if user.user_type == 'farmer':
        if not user.is_approved:
            return render(request, 'accounts/dashboards/waiting_approval.html')
        return redirect('farmer_dashboard')
    elif user.user_type == 'official':
        return redirect('official_dashboard')
    return redirect('login')


# ==========================================
# ۴. پیشخوان جامع پرسنل اداری (نموداری و تحلیلی)
# ==========================================
@login_required
def official_dashboard(request):
    user = request.user
    if user.user_type != 'official':
        return redirect('dashboard')

    managed_region = user.managed_region
    sub_regions = Region.objects.filter(parent=managed_region) if managed_region else []

    context = {
        'office_level_display': user.get_office_level_display(),
        'position_display': user.get_position_display(),
        'company_name': user.company.name if user.company else "نامشخص",
        'org_type': user.company.org_type if user.company else None,
        'managed_region': managed_region,
        'sub_regions': sub_regions,
    }

    all_sub_region_ids = managed_region.get_all_subregions_ids() if managed_region else []

    if user.can_approve_farmers:
        context['total_farmers_count'] = CustomUser.objects.filter(
            user_type='farmer', chosen_region_id__in=all_sub_region_ids, is_approved=True
        ).count()
        context['pending_farmers'] = CustomUser.objects.filter(
            user_type='farmer', chosen_region_id__in=all_sub_region_ids, is_approved=False
        )
    else:
        context['total_farmers_count'] = 0
        context['pending_farmers'] = None

    if user.position in ['head', 'deputy', 'group_leader', 'expert']:
        context['my_managed_tasks'] = ExpertTask.objects.filter(
            expert=user, is_active=True
        ).filter(Q(status='pending') | Q(status='pending_assignment')).select_related('activity', 'crop')

        context['pending_tasks_review'] = ExpertTask.objects.filter(
            assigned_by=user, status='submitted'
        ).distinct()

        context['assigned_tasks_history'] = ExpertTask.objects.filter(
            assigned_by=user
        ).select_related('expert', 'activity', 'crop').prefetch_related('target_regions').order_by('-id')

        company_ids = _get_company_and_sub_ids(user.company)
        immediate_positions = IMMEDIATE_SUBORDINATES.get(user.position, [])

        task_subordinates = CustomUser.objects.filter(
            user_type='official', company_id__in=company_ids,
            position__in=immediate_positions, is_active=True,
        ).exclude(id=user.id).select_related('company', 'managed_region').order_by('company__id', 'position')

        for staff in task_subordinates:
            full_name = staff.get_full_name() or staff.username
            pos_display = staff.get_position_display() or "کارشناس"
            comp_name = staff.company.name if staff.company else ""
            staff.custom_full_title = f"{full_name} | {pos_display} ({comp_name})"

        context['my_subordinates'] = task_subordinates

        subordinate_positions = POSITION_HIERARCHY.get(user.position, [])
        raw_subordinates = CustomUser.objects.filter(
            user_type='official', company_id__in=company_ids,
            position__in=subordinate_positions, is_active=True,
        ).exclude(id=user.id).select_related('company', 'managed_region').order_by('company__id', 'position')

        grouped_subordinates = {}
        for staff in raw_subordinates:
            comp = staff.company
            if not comp:
                continue
            if comp.id not in grouped_subordinates:
                grouped_subordinates[comp.id] = {
                    'company_obj': comp, 'company_name': comp.name, 'staff_list': [],
                }
            full_name = staff.get_full_name() or staff.username
            position_title = staff.get_position_display() or "کارشناس"
            staff.custom_full_title = f"{full_name} | {position_title} {comp.name}"
            grouped_subordinates[comp.id]['staff_list'].append(staff)

        context['grouped_subordinates'] = grouped_subordinates.values()

        # این ۵ مقدار داده‌ی نمایشی/ساختگی هستند (placeholder)، نه محاسبه‌ی
        # واقعی. قبل از رفتن به production باید با کوئری واقعی جایگزین شوند
        # یا حذف شوند - در حال حاضر می‌توانند کاربر را گمراه کنند.
        context['survey_completed'] = 65
        context['survey_pending'] = 20
        context['survey_incomplete'] = 15
        context['productivity_index_water'] = 1.42
        context['productivity_index_soil'] = 2.30

        region_labels = []
        region_progress_data = []
        for s_region in sub_regions:
            region_labels.append(s_region.name)
            tasks = ExpertTask.objects.filter(target_regions=s_region)
            approved_count = tasks.filter(status='approved').count()
            total_count = tasks.count()
            pct = (approved_count / total_count * 100) if total_count > 0 else 0
            region_progress_data.append(round(pct))

        context['region_labels'] = region_labels
        context['region_progress_data'] = region_progress_data
    else:
        my_tasks = ExpertTask.objects.filter(expert=user, is_active=True).select_related('activity', 'crop')
        context['my_tasks'] = my_tasks
        context['pending_tasks_count'] = my_tasks.filter(status='pending').count()
        context['approved_tasks_count'] = my_tasks.filter(status='approved').count()
        context['rejected_tasks_count'] = my_tasks.filter(status='rejected').count()

    context['current_time'] = timezone.now()
    context['revoke_limit_hours'] = 48

    return render(request, 'accounts/dashboards/official_dashboard.html', context)


# ==========================================
# ۵. اکشن‌های نظارتی، ارجاع و چرخه تایید سلسله‌مراتب معکوس
# ==========================================
@login_required
@require_POST
def approve_farmer(request, farmer_id):
    """
    اصلاح شد:
    - قبلاً فقط user_type و position چک می‌شد؛ فلگ can_approve_farmers
      (که در داشبورد برای تصمیم‌گیری استفاده می‌شود) اصلاً بررسی نمی‌شد.
    - هیچ محدودیت جغرافیایی وجود نداشت؛ هر مدیر می‌توانست هر کشاورزی در کل
      کشور را تایید کند. حالا کشاورز باید داخل زیرمجموعه‌ی منطقه‌ی مدیریتی
      کاربر جاری باشد.
    """
    user = request.user
    if not (user.user_type == 'official' and user.can_approve_farmers):
        messages.error(request, "شما اجازه‌ی تایید صلاحیت کشاورزان را ندارید.")
        return redirect('official_dashboard')

    if not user.managed_region:
        messages.error(request, "برای شما منطقه‌ی مدیریتی تعریف نشده است.")
        return redirect('official_dashboard')

    allowed_region_ids = user.managed_region.get_all_subregions_ids()
    farmer = get_object_or_404(
        CustomUser, id=farmer_id, user_type='farmer', chosen_region_id__in=allowed_region_ids
    )
    farmer.is_approved = True
    farmer.save()
    messages.success(request, f"حساب کاربری کشاورز {farmer.get_full_name()} با موفقیت فعال شد.")
    return redirect('official_dashboard')


@login_required
@require_POST
def assign_sub_task_view(request, task_id):
    """
    موتور ارجاع آبشاری و زنجیره‌ای.

    اصلاح شد:
    - sub_activity_id قبلاً بدون هیچ اعتبارسنجی مستقیماً به activity_id تسک
      جدید تبدیل می‌شد؛ یعنی کاربر می‌توانست هر شناسه‌ی فعالیتی (حتی خارج از
      زیردرخت فعالیت والد) را ارسال کند. حالا با
      _get_activity_and_descendant_ids بررسی می‌شود.
    - region_ids قبلاً بدون چک به target_regions تخصیص داده می‌شد. حالا باید
      داخل قلمرو مدیریتی/فعالیت زیردست باشد (همان منطقی که سیگنال
      validate_task_regions_integrity هم اعمال می‌کند، اینجا صریح‌تر چک شده).
    - خطای داخلی دیگر با str(e) خام به کاربر نمایش داده نمی‌شود.
    """
    parent_task = get_object_or_404(ExpertTask, id=task_id, expert=request.user)

    subordinate_ids = request.POST.getlist('subordinate_id[]')
    region_ids = request.POST.getlist('sub_task_region[]')
    sub_activity_ids = request.POST.getlist('sub_activity_id[]')

    if not subordinate_ids:
        single_sub_id = request.POST.get('subordinate_id')
        if single_sub_id:
            subordinate_ids = [single_sub_id]
            region_ids = request.POST.getlist('regions') or request.POST.getlist('sub_task_region[]')
            single_sub_act = request.POST.get('sub_activity_id')
            sub_activity_ids = [single_sub_act] if single_sub_act else []

    if not subordinate_ids:
        messages.error(request, "هیچ کارشناسی جهت تقسیم و ارجاع کار انتخاب نشده است.")
        return redirect('official_dashboard')

    company_ids = _get_company_and_sub_ids(request.user.company)
    immediate_positions = IMMEDIATE_SUBORDINATES.get(request.user.position, [])
    allowed_activity_ids = set(_get_activity_and_descendant_ids(parent_task.activity))

    success_count = 0

    try:
        with transaction.atomic():
            for i, sub_id in enumerate(subordinate_ids):
                if not sub_id:
                    continue

                subordinate = get_object_or_404(
                    CustomUser, id=sub_id, user_type='official',
                    company_id__in=company_ids, position__in=immediate_positions,
                )

                is_target_staff = (subordinate.position == 'staff')

                current_sub_act_id = (
                    sub_activity_ids[i] if i < len(sub_activity_ids) and sub_activity_ids[i] else None
                )

                if current_sub_act_id == 'ALL_ACTIVITY' or not current_sub_act_id:
                    target_activity_id = parent_task.activity.id
                else:
                    target_activity_id = int(current_sub_act_id)
                    if target_activity_id not in allowed_activity_ids:
                        messages.error(
                            request,
                            "فعالیت انتخاب‌شده خارج از زیرمجموعه‌ی فعالیت مادر است و رد شد.",
                        )
                        continue

                sub_task = ExpertTask.objects.create(
                    expert=subordinate,
                    activity_id=target_activity_id,
                    crop=parent_task.crop,
                    assigned_by=request.user,
                    parent_task=parent_task,
                    status='pending' if is_target_staff else 'pending_assignment',
                )

                # اعتبارسنجی منطقه: باید داخل قلمرو منطقه‌ی مدیریتی کارشناس
                # هدف یا قلمرو خود کاربر جاری باشد.
                candidate_region_id = region_ids[i] if i < len(region_ids) and region_ids[i] else None
                if candidate_region_id:
                    allowed_region_ids = (
                        subordinate.managed_region.get_all_subregions_ids()
                        if subordinate.managed_region else
                        (request.user.managed_region.get_all_subregions_ids()
                         if request.user.managed_region else [])
                    )
                    if int(candidate_region_id) in allowed_region_ids:
                        sub_task.target_regions.set([candidate_region_id])
                    elif subordinate.managed_region:
                        sub_task.target_regions.set([subordinate.managed_region])
                elif subordinate.managed_region:
                    sub_task.target_regions.set([subordinate.managed_region])

                success_count += 1

            if success_count > 0:
                parent_task.status = 'pending_assignment'
                parent_task.save()
                messages.success(
                    request, f"تعداد {success_count} ابلاغیه تفکیکی با تخصیص وظایف مربوطه با موفقیت صادر شد."
                )
            else:
                messages.warning(request, "داده‌های ارسالی فرم نامعتبر بود و وظیفه‌ای ثبت نگردید.")

    except Exception:
        logger.exception("خطا در assign_sub_task_view برای task_id=%s", task_id)
        messages.error(request, "خطای سیستمی در فرآیند تقسیم کار رخ داد. لطفاً دوباره تلاش کنید.")

    return redirect('official_dashboard')


@login_required
@require_POST
def revoke_assigned_task_view(request, task_id):
    """لغو ارجاع اشتباه توسط مدیر فرستنده (حداکثر تا ۴۸ ساعت)."""
    task = get_object_or_404(ExpertTask, id=task_id, assigned_by=request.user)

    if timezone.now() > task.created_at + timedelta(hours=48):
        messages.error(request, "زمان مجاز برای حذف و بازگرداندن این ابلاغیه (۴۸ ساعت) به پایان رسیده است.")
        return redirect('official_dashboard')

    if task.status not in ['pending', 'pending_assignment']:
        messages.error(request, "این فعالیت توسط کارشناس مربوطه تغییر وضعیت یافته و دیگر قابل لغو نیست.")
        return redirect('official_dashboard')

    try:
        with transaction.atomic():
            parent_task = task.parent_task
            task.delete()
            if parent_task and not parent_task.sub_tasks.exists():
                parent_task.status = 'pending'
                parent_task.save()
        messages.success(request, "ابلاغیه ارسالی با موفقیت حذف شد و فعالیت به کارتابل شما بازگشت.")
    except Exception:
        logger.exception("خطا در revoke_assigned_task_view برای task_id=%s", task_id)
        messages.error(request, "خطا در لغو ابلاغیه. لطفاً دوباره تلاش کنید.")

    return redirect('official_dashboard')


@login_required
def answer_task_variables_view(request, task_id):
    """فرم پاسخ به متغیرهای پویای شاخص‌ها توسط کارشناس عملیاتی (Staff)."""
    task = get_object_or_404(ExpertTask, id=task_id, expert=request.user)
    if task.expert.position != 'staff':
        raise Http404("فقط کارشناس عملیاتی به فرم پاسخ دسترسی دارد.")

    variables = VariableDefinition.objects.filter(activity=task.activity, crop=task.crop)

    if request.method == 'POST':
        try:
            progress = int(request.POST.get('progress_report', 100))
        except (TypeError, ValueError):
            progress = 100
        progress = max(0, min(progress, 100))  # سقف/کف اعمال شود

        submission, _created = ExpertAnswerSubmission.objects.get_or_create(
            company=request.user.company,
            region=task.target_regions.first() or request.user.managed_region,
            crop=task.crop,
            expert=request.user,
            task=task,  # پیوند مستقیم submission به task - برای رفع مشکل تایید گروهی در review_task
            defaults={'status': 'draft'},
        )

        for var in variables:
            val = request.POST.get(f'var_{var.id}')
            if val is None:
                continue
            try:
                # فیلد ExpertAnswerDetail.value از نوع DecimalField است؛
                # float() می‌تواند خطای دقت اعشاری ایجاد کند و برای ورودی
                # نامعتبر هم Exception خام بالا می‌رفت. حالا Decimal با
                # اعتبارسنجی صریح استفاده می‌شود.
                decimal_val = Decimal(val)
            except (InvalidOperation, ValueError):
                messages.error(request, f"مقدار وارد شده برای «{var.name}» نامعتبر است.")
                continue
            detail, _d_created = ExpertAnswerDetail.objects.get_or_create(submission=submission, variable=var)
            detail.value = decimal_val
            detail.save()

        task.status = 'submitted'
        task.progress_report = progress
        task.save()

        messages.success(request, "داده‌های عددی ثبت و جهت بررسی به مدیر بالادست ارسال شدند.")
        return redirect('official_dashboard')

    return render(request, 'accounts/dashboards/answer_variables.html', {'task': task, 'variables': variables})


@login_required
@require_POST
def review_task(request, task_id):
    """
    موتور گردش کار معکوس: تایید یا رد زنجیره‌ای گزارش‌ها.

    اصلاح شد:
    - قبلاً هیچ چک مالکیتی نبود: هر کاربر با سمت مدیریتی می‌توانست هر task_id
      دلخواه را (حتی از شاخه‌ی دیگر چارت) تایید/رد کند. حالا get_object_or_404
      با assigned_by=request.user فیلتر می‌شود.
    - قبلاً وضعیت فعلی تسک چک نمی‌شد؛ یک تسک 'approved' هم دوباره قابل 'رد
      شدن' بود. حالا فقط task در وضعیت 'submitted' قابل بررسی است.
    - تایید یک زیرتسک قبلاً بی‌قیدوشرط والد را 'submitted' می‌کرد، حتی اگر
      خواهر/برادرهای دیگرش هنوز تایید نشده بودند. حالا والد فقط وقتی
      submitted می‌شود که همه‌ی زیرتسک‌ها approved باشند.
    - reviewed_by/reviewed_at ثبت می‌شود.
    """
    task = get_object_or_404(
        ExpertTask, id=task_id, assigned_by=request.user, status='submitted'
    )

    if request.user.position not in ['head', 'deputy', 'group_leader', 'expert']:
        messages.error(request, "شما اجازه‌ی بررسی این وظیفه را ندارید.")
        return redirect('official_dashboard')

    action = request.POST.get('action')
    comment = request.POST.get('manager_comment', '')

    if action == 'rejected':
        if not comment.strip():
            messages.error(request, "ذکر دلیل رد سازمانی برای بازگرداندن فعالیت الزامی است.")
            return redirect('official_dashboard')

        task.status = 'rejected'
        task.manager_comment = comment
        task.reviewed_by = request.user
        task.reviewed_at = timezone.now()
        task.save()

        task.sub_tasks.update(status='rejected', manager_comment=f"رد شده در سطح بالا: {comment}")
        messages.warning(request, "گزارش رد شد و جهت اصلاح مجدد مقادیر به رده‌ی پایین ارجاع یافت.")

    elif action == 'approved':
        task.status = 'approved'
        task.reviewed_by = request.user
        task.reviewed_at = timezone.now()
        task.save()

        if task.parent_task:
            parent = task.parent_task
            # فقط وقتی همه‌ی زیرتسک‌های فعال این والد تایید شده باشند، والد
            # به مرحله‌ی بعد (submitted) می‌رود؛ نه با تایید اولین‌شان.
            all_children_approved = not parent.sub_tasks.filter(is_active=True).exclude(status='approved').exists()
            if all_children_approved:
                parent.status = 'submitted'
                parent.save()
                messages.success(request, "تمام زیروظایف تایید شدند و وظیفه به مدیر رده بالاتر ارجاع یافت.")
            else:
                messages.success(request, "تایید شما ثبت شد. در انتظار تایید بقیه‌ی زیروظایف هستیم.")
        else:
            activity = task.activity
            activity.verified_progress = task.progress_report
            activity.save()

            # اصلاح شد: حالا ابتدا submissionهای مستقیماً مرتبط با همین task
            # (از طریق فیلد جدید ExpertAnswerSubmission.task) verified
            # می‌شوند. فقط اگر هیچ submission مستقیمی پیدا نشد (یعنی داده‌ی
            # قدیمی قبل از افزودن فیلد task است)، به رفتار قدیمی بر اساس
            # (crop, expert) بازمی‌گردیم تا داده‌ی تاریخی گم نشود.
            direct_submissions = ExpertAnswerSubmission.objects.filter(task=task)
            if direct_submissions.exists():
                direct_submissions.update(status='verified')
            else:
                ExpertAnswerSubmission.objects.filter(
                    crop=task.crop, expert=task.expert, task__isnull=True,
                ).update(status='verified')

            messages.success(
                request,
                "تایید نهایی با موفقیت صادر شد. فرم‌ها قفل شده و بر روی محاسبات شاخص‌ها اعمال گردیدند.",
            )
    else:
        messages.error(request, "اقدام نامعتبر است.")

    return redirect('official_dashboard')


# ==========================================
# ۶. مدیریت ساختاریافته و شرکتی دسترسی‌ها (Company & Position Based)
# ==========================================
@login_required
def manage_permissions_view(request):
    user = request.user

    if user.user_type != 'official' or user.position not in ['head', 'deputy', 'group_leader']:
        return redirect('official_dashboard')

    if not user.company:
        context = {'grouped_companies': [], 'error_message': "شرکت یا دفتر سازمانی شما مشخص نشده است."}
        return render(request, 'accounts/dashboards/manage_permissions.html', context)

    company_ids = _get_company_and_sub_ids(user.company)
    subordinate_positions = POSITION_HIERARCHY.get(user.position, [])

    if request.method == 'POST':
        target_user_id = request.POST.get('user_id')
        can_approve = request.POST.get('can_approve_farmers') == 'true'

        # اصلاح شد: قبلاً فقط company_id__in چک می‌شد، یعنی یک group_leader
        # می‌توانست دسترسی معاون یا حتی خودش را تغییر دهد (چون همه در یک
        # company_id هستند). حالا position__in هم اعمال می‌شود تا فقط
        # واقعاً زیردستان مجاز قابل تغییر باشند.
        target_user = get_object_or_404(
            CustomUser, id=target_user_id, company_id__in=company_ids,
            position__in=subordinate_positions,
        )
        target_user.can_approve_farmers = can_approve
        target_user.save()
        return JsonResponse({'status': 'success', 'message': 'دسترسی با موفقیت تغییر یافت.'})

    all_staff = CustomUser.objects.filter(
        user_type='official', company_id__in=company_ids,
        position__in=subordinate_positions, is_active=True,
    ).exclude(id=user.id).select_related('managed_region', 'company').order_by('company__id', 'position')

    grouped_companies = {}
    for staff in all_staff:
        comp = staff.company
        if not comp:
            continue
        if comp.id not in grouped_companies:
            grouped_companies[comp.id] = {
                'company_obj': comp, 'company_name': comp.name, 'staff_list': [],
            }
        full_name = staff.get_full_name() or staff.username
        position_title = staff.get_position_display() or "کارشناس"
        staff.custom_full_title = f"{full_name} | {position_title} {comp.name}"
        grouped_companies[comp.id]['staff_list'].append(staff)

    context = {
        'company_name': user.company.name,
        'grouped_companies': grouped_companies.values(),
    }
    return render(request, 'accounts/dashboards/manage_permissions.html', context)


# ==========================================
# ۷. پیشخوان اختصاصی کشاورز (Farmer Dashboard)
# ==========================================
@login_required
def farmer_dashboard(request):
    user = request.user
    if user.user_type != 'farmer' or not user.is_approved:
        return redirect('dashboard')

    context = {'farmer_region': user.chosen_region}
    return render(request, 'accounts/dashboards/farmer_dashboard.html', context)
