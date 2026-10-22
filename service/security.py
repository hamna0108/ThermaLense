"""Security module for whitelisted AST expression parsing and safe evaluation.

Disallows eval, exec, sympify, imports, and arbitrary attribute access.
Allowed grammar:
- Variables: x, t
- Constants: pi, numeric literals (int, float)
- Operators: +, -, *, /, **, unary +, unary -
- Functions: sin, cos, exp, sqrt
- Parentheses
- Max length: 200 characters
"""

import ast
import numpy as np

MAX_EXPR_LENGTH = 200
ALLOWED_VARS = {"x", "t"}
ALLOWED_CONSTANTS = {"pi": np.pi}
ALLOWED_FUNCTIONS = {
    "sin": np.sin,
    "cos": np.cos,
    "exp": np.exp,
    "sqrt": np.sqrt
}

ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.UAdd,
    ast.USub
)

class SecurityError(ValueError):
    """Raised when an expression contains unauthorized AST nodes, identifiers, or exceeds length."""
    pass

ExpressionSecurityError = SecurityError

class WhitelistASTValidator(ast.NodeVisitor):
    """Validates that an AST contains ONLY whitelisted syntax elements."""

    def visit(self, node):
        if not isinstance(node, ALLOWED_NODE_TYPES):
            raise SecurityError(
                f"Disallowed syntax element: '{type(node).__name__}'. Only basic arithmetic and whitelisted functions are permitted."
            )
        super().visit(node)

    def visit_Name(self, node: ast.Name):
        if node.id.startswith("__"):
            raise SecurityError(f"Disallowed dunder access: '{node.id}'")
        if node.id not in ALLOWED_VARS and node.id not in ALLOWED_CONSTANTS and node.id not in ALLOWED_FUNCTIONS:
            raise SecurityError(
                f"Disallowed identifier: '{node.id}'. Only variables (x, t), constants (pi), and functions (sin, cos, exp, sqrt) are allowed."
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name):
            raise SecurityError("Computed or indirect function calls are strictly forbidden.")
        if node.func.id not in ALLOWED_FUNCTIONS:
            raise SecurityError(
                f"Disallowed function call: '{node.func.id}()'. Only {list(ALLOWED_FUNCTIONS.keys())} are allowed."
            )
        if len(node.args) != 1:
            raise SecurityError(
                f"Function '{node.func.id}' requires exactly 1 argument (received {len(node.args)})."
            )
        if node.keywords:
            raise SecurityError("Keyword arguments in expressions are strictly forbidden.")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise SecurityError(f"Disallowed non-numeric constant type: '{type(node.value).__name__}'")
        self.generic_visit(node)

def _evaluate_ast_node(node: ast.AST, env: dict):
    """Recursively evaluates a validated AST node without eval() or exec()."""
    if isinstance(node, ast.Expression):
        return _evaluate_ast_node(node.body, env)
    
    if isinstance(node, ast.Constant):
        return node.value
    
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return np.pi
        if node.id in env:
            return env[node.id]
        raise SecurityError(f"Unbound variable: '{node.id}'")
    
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_ast_node(node.operand, env)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
        raise SecurityError(f"Unsupported unary operator: '{type(node.op).__name__}'")
    
    if isinstance(node, ast.BinOp):
        left = _evaluate_ast_node(node.left, env)
        right = _evaluate_ast_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.Pow):
            return left ** right
        raise SecurityError(f"Unsupported binary operator: '{type(node.op).__name__}'")
    
    if isinstance(node, ast.Call):
        fn_name = node.func.id
        fn = ALLOWED_FUNCTIONS.get(fn_name)
        if fn is None:
            raise SecurityError(f"Unknown function '{fn_name}'")
        arg_val = _evaluate_ast_node(node.args[0], env)
        return fn(arg_val)
    
    raise SecurityError(f"Unsupported AST node for evaluation: '{type(node).__name__}'")

def parse_whitelisted_expression(expr_str: str):
    """Parses and validates a mathematical expression string, returning a safe callable f(x, t=0.0).
    
    Raises:
        SecurityError: If expression is too long, contains syntax errors, or breaches the whitelist.
    """
    if not isinstance(expr_str, str):
        raise SecurityError("Expression must be a string.")
    
    clean_expr = expr_str.strip()
    if not clean_expr:
        raise SecurityError("Expression cannot be empty.")
        
    if len(clean_expr) > MAX_EXPR_LENGTH:
        raise SecurityError(
            f"Expression exceeds maximum permitted length of {MAX_EXPR_LENGTH} characters (received {len(clean_expr)})."
        )
    
    try:
        parsed_ast = ast.parse(clean_expr, mode='eval')
    except SyntaxError as e:
        raise SecurityError(f"Mathematical expression syntax error: {e.msg} at column {e.offset}")
    
    # Run AST whitelist validator
    validator = WhitelistASTValidator()
    validator.visit(parsed_ast)
    
    # Return vectorized evaluator closure
    def safe_callable(x=0.0, t=0.0):
        # Convert to numpy arrays or floats
        x_val = np.asarray(x, dtype=float) if isinstance(x, (list, tuple, np.ndarray)) else float(x)
        t_val = np.asarray(t, dtype=float) if isinstance(t, (list, tuple, np.ndarray)) else float(t)
        env = {"x": x_val, "t": t_val}
        res = _evaluate_ast_node(parsed_ast, env)
        if isinstance(x, np.ndarray) and (np.isscalar(res) or (isinstance(res, np.ndarray) and res.ndim == 0)):
            return np.full_like(x, float(res), dtype=float)
        if isinstance(t, np.ndarray) and (np.isscalar(res) or (isinstance(res, np.ndarray) and res.ndim == 0)):
            return np.full_like(t, float(res), dtype=float)
        return res
    return safe_callable
