import ast
import operator

MAX_LEN = 100

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
_UN_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def parse_literal(value: str):
    """ИСПРАВЛЕНО (B307): ast.literal_eval разбирает только литералы
    (числа, строки, списки, словари) и не выполняет код."""
    return ast.literal_eval(value)


def calculate(expression: str):
    """Безопасный калькулятор вместо eval: разбираем AST и разрешаем
    только числа и арифметические операторы + - * / %."""
    if len(expression) > MAX_LEN:
        raise ValueError("expression too long")
    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


def _eval(node):
    if (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN_OPS:
        return _UN_OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")
