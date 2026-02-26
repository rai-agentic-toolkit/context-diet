"""
Integration tests for the distill() entrypoint: budget edge cases,
strategy dispatch, filename/extension hints, and token counter wiring.
"""

import json
import warnings

import pytest

from context_diet import distill
from context_diet.interfaces import ContextBudgetExceededError
from context_diet.token_utils import default_token_heuristic


# ---------------------------------------------------------------------------
# Budget edge cases
# ---------------------------------------------------------------------------


def test_zero_budget_returns_empty():
    result = distill("any content at all", budget=0)
    assert result == ""


def test_negative_budget_returns_empty():
    result = distill("any content", budget=-1)
    assert result == ""


def test_large_budget_passes_through_small_content():
    content = '{"key": "value"}'
    result = distill(content, budget=100_000, token_counter=default_token_heuristic)
    parsed = json.loads(result)
    assert parsed["key"] == "value"


# ---------------------------------------------------------------------------
# Default token counter warning
# ---------------------------------------------------------------------------


def test_default_token_counter_emits_runtime_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        distill("hello world", budget=500)
    assert any(issubclass(w.category, RuntimeWarning) for w in caught)


def test_custom_token_counter_suppresses_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        distill("hello world", budget=500, token_counter=default_token_heuristic)
    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert len(runtime_warnings) == 0


# ---------------------------------------------------------------------------
# Explicit strategy bypasses sniffer
# ---------------------------------------------------------------------------


def test_explicit_json_strategy_on_json_content():
    # Each {"id": N} is ~2 tokens; 50 items = ~100 tokens. Use budget=40 to force truncation.
    data = [{"id": i} for i in range(50)]
    content = json.dumps(data)
    result = distill(content, budget=40, strategy="json", token_counter=default_token_heuristic)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) < 50


def test_explicit_text_strategy_on_any_content():
    # Even JSON-looking content uses plain text when strategy="text"
    content = '{"key": "value"}' * 200
    result = distill(content, budget=20, strategy="text", token_counter=default_token_heuristic)
    assert len(result) <= 20 * 4 + 50  # rough upper bound with marker


# ---------------------------------------------------------------------------
# Filename and extension dispatch
# ---------------------------------------------------------------------------


def test_filename_py_extension_uses_python_strategy():
    python_code = '''
def hello():
    """Say hello."""
    print("Hello, world!")

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
'''
    result = distill(
        python_code,
        budget=50,
        filename="script.py",
        token_counter=default_token_heuristic,
    )
    # Python strategy should be dispatched; result is valid Python
    assert "def hello" in result or "def goodbye" in result or "..." in result


def test_filename_sql_extension_uses_sql_strategy():
    sql_content = """
CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));
INSERT INTO users VALUES (1, 'Alice');
INSERT INTO users VALUES (2, 'Bob');
"""
    result = distill(
        sql_content,
        budget=200,
        filename="schema.sql",
        token_counter=default_token_heuristic,
    )
    assert "CREATE TABLE" in result
    assert "INSERT" not in result


def test_extension_without_dot_is_normalised():
    content = '{"items": [1, 2, 3]}'
    result = distill(
        content,
        budget=500,
        extension="json",
        token_counter=default_token_heuristic,
    )
    parsed = json.loads(result)
    assert parsed["items"] == [1, 2, 3]


def test_extension_with_dot_prefix():
    content = '{"x": 1}'
    result = distill(
        content,
        budget=500,
        extension=".json",
        token_counter=default_token_heuristic,
    )
    assert json.loads(result)["x"] == 1
