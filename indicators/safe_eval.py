"""
indicators/safe_eval.py

جایگزین امن برای eval() خام روی فرمول‌های کاربر در IndicatorDefinition.

چرا eval قبلی امن نبود؟
    eval(formula, {"__builtins__": None}, context)
حتی با __builtins__=None، در پایتون می‌توان به اشیای داخلی از طریق زنجیره‌ی
attributeها رسید، مثلاً:
    ().__class__.__base__.__subclasses__()
و از آنجا به کلاس‌هایی رسید که امکان اجرای دستور سیستمی می‌دهند. این یک
sandbox escape شناخته‌شده است، نه یک باگ نظری.

راه‌حل این فایل: به‌جای اجرای مستقیم رشته، آن را با ماژول `ast` پارس می‌کنیم
و فقط گره‌هایی (Node) از یک لیست سفید محدود (اعداد، عملگرهای ریاضی/مقایسه‌ای/
منطقی، and/or/not، شرط تک‌خطی، و صدا زدن چند تابع مشخص مثل min/max/round/abs)
را اجرا می‌کنیم. هیچ Attribute access، Import، Call به تابع دلخواه، یا
Subscript اجازه اجرا ندارد.

نصب جایگزین: اگر ترجیح می‌دهید به‌جای نوشتن دستی این ماژول از یک کتابخانه‌ی
آماده استفاده کنید، `pip install simpleeval` هم گزینه‌ی خوبی است و رابط
مشابهی دارد.
"""
import ast
import math
import operator

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_ALLOWED_COMPARE = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}

_ALLOWED_FUNCS = {
    'min': min,
    'max': max,
    'round': round,
    'abs': abs,
    'sqrt': math.sqrt,
    'floor': math.floor,
    'ceil': math.ceil,
}


class UnsafeExpressionError(Exception):
    """فرمول شامل چیزی خارج از لیست سفید مجاز بود."""


def _eval_node(node, context):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpressionError(f"مقدار ثابت غیرمجاز: {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise UnsafeExpressionError(f"متغیر تعریف‌نشده: {node.id}")

    if isinstance(node, ast.BinOp):
        op_func = _ALLOWED_BINOPS.get(type(node.op))
        if not op_func:
            raise UnsafeExpressionError(f"عملگر غیرمجاز: {type(node.op).__name__}")
        return op_func(_eval_node(node.left, context), _eval_node(node.right, context))

    if isinstance(node, ast.UnaryOp):
        op_func = _ALLOWED_UNARYOPS.get(type(node.op))
        if not op_func:
            raise UnsafeExpressionError(f"عملگر یگانه غیرمجاز: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand, context))

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for v in values:
                result = result or v
            return result
        raise UnsafeExpressionError("عملگر منطقی غیرمجاز")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            op_func = _ALLOWED_COMPARE.get(type(op))
            if not op_func:
                raise UnsafeExpressionError(f"عملگر مقایسه‌ای غیرمجاز: {type(op).__name__}")
            right = _eval_node(comparator, context)
            result = result and op_func(left, right)
            left = right
        return result

    if isinstance(node, ast.IfExp):
        # پشتیبانی از عبارت شرطی: value_if_true if condition else value_if_false
        return _eval_node(node.body, context) if _eval_node(node.test, context) else _eval_node(node.orelse, context)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise UnsafeExpressionError("فراخوانی تابع غیرمجاز است.")
        if node.keywords:
            raise UnsafeExpressionError("آرگومان کلیدی مجاز نیست.")
        args = [_eval_node(arg, context) for arg in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)

    raise UnsafeExpressionError(f"ساختار غیرمجاز در فرمول: {type(node).__name__}")


def safe_eval_formula(formula: str, context: dict):
    """
    فرمول را با لیست سفید امن ارزیابی می‌کند.
    در صورت وجود هر ساختار خارج از لیست مجاز، UnsafeExpressionError raise می‌شود.
    """
    tree = ast.parse(formula, mode='eval')
    return _eval_node(tree, context)
