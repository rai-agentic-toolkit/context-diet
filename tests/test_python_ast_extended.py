"""
Extended coverage for PythonAstDietStrategy: async functions, decorators,
focus_on kwarg, skeleton mode edge cases, and multiple-function files.
"""

import pytest

from context_diet.interfaces import ContextBudgetExceededError
from context_diet.strategies.python_ast import PythonAstDietStrategy
from context_diet.token_utils import default_token_heuristic


@pytest.fixture()
def strategy():
    return PythonAstDietStrategy()


# ---------------------------------------------------------------------------
# Pass-through when content fits budget
# ---------------------------------------------------------------------------


def test_small_function_within_budget_returned(strategy):
    content = "def add(a, b):\n    return a + b\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "return a + b" in result


# ---------------------------------------------------------------------------
# Scrub mode — docstrings removed, bodies kept
# ---------------------------------------------------------------------------


def test_scrub_removes_function_docstring(strategy):
    content = 'def greet(name):\n    """Say hello."""\n    return f"Hello {name}"\n'
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "Say hello." not in result
    assert 'return f"Hello {name}"' in result


def test_scrub_removes_module_docstring(strategy):
    content = '"""Top-level module doc."""\n\ndef foo():\n    return 1\n'
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "Top-level module doc." not in result
    assert "def foo" in result


def test_scrub_removes_class_docstring(strategy):
    content = 'class Foo:\n    """Foo class."""\n    x = 1\n'
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "Foo class." not in result
    assert "x = 1" in result


# ---------------------------------------------------------------------------
# Skeleton mode — bodies replaced with ...
# ---------------------------------------------------------------------------


def test_skeleton_mode_replaces_body_with_ellipsis(strategy):
    # scrubbed = 10 tokens; budget=9 forces skeleton (6 tokens) to be used
    content = "def compute(x):\n    y = x * x\n    return y\n"
    result = strategy.compress(content, budget=9, token_counter=default_token_heuristic)
    assert "..." in result
    assert "y = x * x" not in result


def test_skeleton_mode_preserves_function_signature(strategy):
    # greet skeleton = 15 tokens; budget=16 triggers skeleton (scrubbed > 16)
    content = "def greet(name: str, greeting: str = 'Hello') -> str:\n    return f'{greeting} {name}'\n"
    result = strategy.compress(content, budget=16, token_counter=default_token_heuristic)
    assert "def greet" in result
    assert "name" in result
    assert "..." in result


def test_skeleton_mode_multiple_functions(strategy):
    content = (
        "def alpha():\n    x = 1\n    return x\n\n"
        "def beta():\n    y = 2\n    return y\n\n"
        "def gamma():\n    z = 3\n    return z\n"
    )
    result = strategy.compress(content, budget=20, token_counter=default_token_heuristic)
    assert "def alpha" in result
    assert "def beta" in result
    assert "def gamma" in result
    assert result.count("...") >= 3


# ---------------------------------------------------------------------------
# Async function handling
# ---------------------------------------------------------------------------


def test_async_function_in_scrub_mode_body_kept(strategy):
    content = 'async def fetch(url: str) -> str:\n    """Fetch a URL."""\n    return url\n'
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "async def fetch" in result
    assert "return url" in result
    assert "Fetch a URL." not in result


def test_async_function_in_skeleton_mode_gets_ellipsis(strategy):
    content = (
        "async def fetch(url: str) -> str:\n"
        "    import httpx\n"
        "    response = await httpx.get(url)\n"
        "    return response.text\n"
    )
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    assert "async def fetch" in result
    assert "..." in result
    assert "response.text" not in result


# ---------------------------------------------------------------------------
# Decorator preservation
# ---------------------------------------------------------------------------


def test_decorator_preserved_in_scrub_mode(strategy):
    content = "@property\ndef value(self):\n    return self._value\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "@property" in result


def test_decorator_preserved_in_skeleton_mode(strategy):
    # skeleton = 12 tokens; use budget=13 (scrubbed ~22 tokens > 13, skeleton 12 <= 13)
    content = (
        "@staticmethod\n"
        "def compute(x: int) -> int:\n"
        "    result = x ** 2 + x + 1\n"
        "    return result\n"
    )
    result = strategy.compress(content, budget=13, token_counter=default_token_heuristic)
    assert "@staticmethod" in result
    assert "..." in result


# ---------------------------------------------------------------------------
# focus_on kwarg — keep one function's body
# ---------------------------------------------------------------------------


def test_focus_on_keeps_target_body(strategy):
    content = (
        "def helper():\n    return 42\n\n"
        "def main():\n    x = helper()\n    return x\n"
    )
    result = strategy.compress(
        content, budget=20, token_counter=default_token_heuristic, focus_on="main"
    )
    # main's body is kept; helper is skeletonized
    assert "def main" in result
    assert "x = helper()" in result
    assert "def helper" in result


def test_focus_on_skeletonizes_non_target(strategy):
    # scrubbed = 17 tokens; focus_skeleton = 13 tokens; budget=15 forces skeleton
    content = (
        "def helper():\n    x = 1\n    return x\n\n"
        "def main():\n    return helper()\n"
    )
    result = strategy.compress(
        content, budget=15, token_counter=default_token_heuristic, focus_on="main"
    )
    # helper's body should be replaced with ...
    assert "x = 1" not in result


# ---------------------------------------------------------------------------
# Invalid Python — ContextBudgetExceededError
# ---------------------------------------------------------------------------


def test_syntax_error_raises_context_budget_exceeded(strategy):
    content = "def bad_func(\n    return 1\n"
    with pytest.raises(ContextBudgetExceededError, match="SyntaxError"):
        strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)


def test_skeleton_too_large_raises(strategy):
    """A file so large that even the skeleton exceeds the budget raises."""
    # Generate a class with many methods — each method signature costs tokens even as ...
    methods = "\n".join(
        f"    def method_{i}(self, arg_{i}: str) -> str:\n        return arg_{i}\n"
        for i in range(500)
    )
    content = f"class Huge:\n{methods}\n"
    with pytest.raises(ContextBudgetExceededError, match="Minimum Python skeleton exceeds budget"):
        strategy.compress(content, budget=1, token_counter=default_token_heuristic)
