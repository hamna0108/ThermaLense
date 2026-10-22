"""Tests for whitelisted AST expression parser and security boundary."""

import pytest
import numpy as np
from service.security import parse_whitelisted_expression, SecurityError

def test_safe_math_expressions():
    # 1. Fundamental harmonic
    f1 = parse_whitelisted_expression("sin(pi * x)")
    assert abs(f1(0.5) - 1.0) < 1e-9
    assert abs(f1(0.0)) < 1e-9

    # 2. Time-dependent diffusion decay
    f2 = parse_whitelisted_expression("sin(pi * x) * exp(-0.1 * pi**2 * t)")
    val = f2(0.5, 1.0)
    expected = 1.0 * np.exp(-0.1 * (np.pi**2) * 1.0)
    assert abs(val - expected) < 1e-9

    # 3. Trigonometric and arithmetic combinations
    f3 = parse_whitelisted_expression("cos(2 * pi * x) + sqrt(x) - (x / 2.0) + 1.5")
    assert np.isfinite(f3(0.25, 0.0))

    # 4. Vectorized array evaluations
    x_arr = np.linspace(0, 1, 11)
    res_arr = f1(x_arr)
    assert isinstance(res_arr, np.ndarray)
    assert len(res_arr) == 11
    assert abs(res_arr[5] - 1.0) < 1e-9

def test_security_rejections():
    # Malicious injection attempts
    injections = [
        "__import__('os')",
        "__import__('os').system('ls')",
        "open('secrets.txt')",
        "eval('2 + 2')",
        "exec('import os')",
        "x.__class__.__bases__[0].__subclasses__()",
        "lambda x: x + 1",
        "import os",
        "[c for c in ()]",
        "{'a': 1}",
        "os.system('whoami')",
        "globals()",
        "locals()",
        "builtins.__dict__"
    ]
    for expr in injections:
        with pytest.raises(SecurityError):
            parse_whitelisted_expression(expr)

def test_max_length_exceeded():
    long_expr = "x + " + "1 + " * 70 + "x"
    assert len(long_expr) > 200
    with pytest.raises(SecurityError) as exc_info:
        parse_whitelisted_expression(long_expr)
    assert "maximum permitted length" in str(exc_info.value)

def test_syntax_errors():
    with pytest.raises(SecurityError) as exc_info:
        parse_whitelisted_expression("sin(pi * x")
    assert "syntax error" in str(exc_info.value).lower()
