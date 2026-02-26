"""
Extended coverage for YamlDietStrategy: empty YAML, comment stripping,
nested content, malformed YAML, and budget error.
"""

import pytest

from context_diet.interfaces import ContextBudgetExceededError
from context_diet.strategies.yaml_diet import YamlDietStrategy
from context_diet.token_utils import default_token_heuristic


@pytest.fixture()
def strategy():
    return YamlDietStrategy()


# ---------------------------------------------------------------------------
# Empty / null content
# ---------------------------------------------------------------------------


def test_empty_yaml_returns_empty_string(strategy):
    """Empty YAML documents (data is None) return an empty string."""
    result = strategy.compress("", budget=100, token_counter=default_token_heuristic)
    assert result == ""


def test_null_yaml_document_returns_empty(strategy):
    """A YAML document that is just '---' or 'null' also yields empty string."""
    result = strategy.compress("null\n", budget=100, token_counter=default_token_heuristic)
    assert result == ""


def test_comments_only_yaml_returns_empty(strategy):
    """A file of only comments parses to None."""
    content = "# This is a comment\n# Another comment\n"
    result = strategy.compress(content, budget=100, token_counter=default_token_heuristic)
    assert result == ""


# ---------------------------------------------------------------------------
# Content within budget — pass-through after comment stripping
# ---------------------------------------------------------------------------


def test_simple_yaml_within_budget(strategy):
    content = "host: localhost\nport: 5432\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "host:" in result
    assert "localhost" in result
    assert "port:" in result


def test_nested_yaml_within_budget(strategy):
    content = "database:\n  host: localhost\n  port: 5432\n  name: mydb\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "database:" in result
    assert "host: localhost" in result


def test_inline_comments_stripped(strategy):
    content = "server:\n  port: 8080  # production port\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "production port" not in result
    assert "port:" in result


def test_block_comments_stripped(strategy):
    content = "# block comment\nkey: value\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "block comment" not in result
    assert "key:" in result


# ---------------------------------------------------------------------------
# Malformed YAML
# ---------------------------------------------------------------------------


def test_malformed_yaml_raises_context_budget_error(strategy):
    """YAML with bad indentation or invalid syntax raises ContextBudgetExceededError."""
    content = "key: value\n  bad_indent: [unclosed\n"
    with pytest.raises(ContextBudgetExceededError, match="Malformed YAML"):
        strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)


def test_tab_indented_yaml_raises(strategy):
    """YAML with tabs (invalid per spec) raises ContextBudgetExceededError."""
    content = "key:\n\t- value\n"
    with pytest.raises(ContextBudgetExceededError, match="Malformed YAML"):
        strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)


# ---------------------------------------------------------------------------
# Budget exceeded
# ---------------------------------------------------------------------------


def test_yaml_exceeds_budget_raises(strategy):
    content = "key: value\nother: data\n"
    with pytest.raises(ContextBudgetExceededError, match="Minimum valid YAML exceeds budget"):
        strategy.compress(content, budget=1, token_counter=default_token_heuristic)


def test_yaml_barely_within_budget_does_not_raise(strategy):
    content = "k: v\n"
    # Should succeed with a reasonable budget
    result = strategy.compress(content, budget=100, token_counter=default_token_heuristic)
    assert "k:" in result


# ---------------------------------------------------------------------------
# YAML list content
# ---------------------------------------------------------------------------


def test_yaml_list_within_budget(strategy):
    content = "items:\n  - one\n  - two\n  - three\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "items:" in result
    assert "one" in result
