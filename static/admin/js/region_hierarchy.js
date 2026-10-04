document.addEventListener('DOMContentLoaded', function() {
    const roleField = document.querySelector('#id_role');
    const regionSelect = document.querySelector('#id_managed_regions');

    if (roleField && regionSelect) {
        roleField.addEventListener('change', function() {
            const role = this.value;

            // اگر مدیر کل شرکت منابع آب بود (Top Manager)
            if (role === 'top_manager') {
                alert("لطفاً استان‌ها را انتخاب کنید؛ سیستم تمام شهرستان‌ها و بخش‌های زیرمجموعه را به صورت خودکار در دیتابیس لحاظ خواهد کرد.");
                // اینجا می‌توان منطق UI برای هایلایت کردن یا انتخاب خودکار تیک‌ها را نوشت
            }
        });
    }
});