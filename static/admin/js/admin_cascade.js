// static/js/cascade_filter.js
(function($) {
    $(document).ready(function() {
        // وقتی لایه ۳ (استان) تغییر کرد، لایه ۴ (شهرستان) فیلتر شود
        $('#id_managed_lv4').set_query_params(function() {
            return {
                parent_id: $('#id_managed_lv3').val(), // مقدار لایه قبل
                level: 4
            };
        });

        // وقتی لایه ۴ (شهرستان) تغییر کرد، لایه ۵ (بخش) فیلتر شود
        $('#id_managed_lv5').set_query_params(function() {
            return {
                parent_id: $('#id_managed_lv4').val(),
                level: 5
            };
        });

        // همین منطق برای لایه ۲ به ۳ و غیره...
    });

    // تابع کمکی برای اضافه کردن پارامتر به Autocomplete جنگو
    $.fn.set_query_params = function(params_func) {
        this.on('select2:opening', function(e) {
            const params = params_func();
            $(this).data('select2').options.options.ajax.data = function(term) {
                return $.extend({
                    term: term.term,
                    page: term.page,
                    app_label: 'accounts',
                    model_name: 'region',
                    field_name: 'parent' // فیلتر بر اساس والد
                }, params);
            };
        });
    };
})(django.jQuery);(function($) {
    $(document).ready(function() {
        // تابع برای اضافه کردن پارامتر والد به درخواست Autocomplete
        function applyFilter(childId, parentId) {
            $(childId).on('select2:opening', function (e) {
                var parentVal = $(parentId).val();
                if (parentVal) {
                    // تزریق پارامتر به تنظیمات Select2
                    $(this).data('select2').options.options.ajax.data = function (params) {
                        return {
                            term: params.term,
                            page: params.page,
                            parent_id: parentVal.toString() // فرستادن ID والد به متد get_search_results
                        };
                    };
                }
            });
        }

        // ۱. فیلتر حوزه (لایه ۲) بر اساس ستاد (لایه ۱)
        applyFilter('#id_managed_lv2', '#id_managed_lv1');
        // ۲. فیلتر استان (لایه ۳) بر اساس حوزه (لایه ۲)
        applyFilter('#id_managed_lv3', '#id_managed_lv2');
        // ۳. فیلتر شهرستان (لایه ۴) بر اساس استان (لایه ۳)
        applyFilter('#id_managed_lv4', '#id_managed_lv3');
        // ۴. فیلتر بخش (لایه ۵) بر اساس شهرستان (لایه ۴)
        applyFilter('#id_managed_lv5', '#id_managed_lv4');
    });
})(django.jQuery);