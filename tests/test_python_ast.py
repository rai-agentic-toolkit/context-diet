"""
Unit tests for the AST Diet Strategy.
"""

from context_diet.strategies.python_ast import PythonAstDietStrategy
from context_diet.token_utils import default_token_heuristic


def test_ast_scrub_mode_removes_docstrings():
    strategy = PythonAstDietStrategy()
    content = '''
"""Module docstring."""

class MyClass:
    """Class docstring."""
    def my_method(self):
        """Method docstring."""
        x = 1
        return x
    '''
    compressed = sorted(
        strategy.compress(content, budget=5000, token_counter=default_token_heuristic).split("\n")
    )
    assert "Module docstring." not in "\n".join(compressed)
    assert "Class docstring." not in "\n".join(compressed)
    assert "Method docstring." not in "\n".join(compressed)
    assert any("x = 1" in line for line in compressed)


def test_ast_skeleton_mode_prunes_implementation():
    strategy = PythonAstDietStrategy()
    content = """
class MyClass:
    def my_method(self):
        print("doing complex things")
        x = 5 + 5
        return x
    """
    # Force skeleton mode by providing a tiny budget but not small enough to trigger text slicing
    compressed = strategy.compress(content, budget=20, token_counter=default_token_heuristic)
    assert "class" in compressed
    assert "MyClass" in compressed
    assert "def" in compressed
    assert "my_method" in compressed
    assert "doing complex things" not in compressed
    assert "x = 5 + 5" not in compressed
    assert "..." in compressed


def test_ast_fallback_on_syntax_error():
    strategy = PythonAstDietStrategy()
    content = """
class MyClass:
    def broken_method(self
        print("missing colon")
    """
    import pytest

    from context_diet.interfaces import ContextBudgetExceededError

    with pytest.raises(ContextBudgetExceededError):
        compressed = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
