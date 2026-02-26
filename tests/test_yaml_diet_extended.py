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
# Progressive depth pruning (the key consistency fix)
# ---------------------------------------------------------------------------


def test_yaml_nested_content_is_pruned_not_raised(strategy):
    """Deep nested YAML that exceeds budget is pruned progressively, never raised."""
    content = (
        "server:\n"
        "  database:\n"
        "    host: localhost\n"
        "    port: 5432\n"
        "    pool:\n"
        "      min: 2\n"
        "      max: 20\n"
        "      timeout: 30\n"
        "  cache:\n"
        "    host: redis\n"
        "    port: 6379\n"
    )
    # Budget too small for full content but not zero
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    assert result != ""
    assert default_token_heuristic(result) <= 10


def test_yaml_depth_pruning_result_is_valid_yaml(strategy):
    """The pruned result must parse as valid YAML."""
    from ruamel.yaml import YAML

    content = (
        "app:\n"
        "  settings:\n"
        "    debug: true\n"
        "    workers: 4\n"
        "    logging:\n"
        "      level: INFO\n"
        "      file: /var/log/app.log\n"
    )
    result = strategy.compress(content, budget=8, token_counter=default_token_heuristic)
    yaml = YAML()
    parsed = yaml.load(result)
    assert parsed is not None


def test_yaml_depth_pruning_preserves_top_level_keys(strategy):
    """After pruning, top-level structure keys survive even if their values are collapsed."""
    content = (
        "database:\n"
        "  host: localhost\n"
        "  credentials:\n"
        "    user: admin\n"
        "    password: secret\n"
        "logging:\n"
        "  level: DEBUG\n"
        "  handlers:\n"
        "    - file\n"
        "    - console\n"
    )
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    assert "database" in result or "logging" in result


def test_yaml_list_structure_is_pruned_not_raised(strategy):
    """A YAML list too large for budget is pruned to an empty list, not raised."""
    content = "items:\n" + "".join(f"  - value_{i}\n" for i in range(50))
    result = strategy.compress(content, budget=5, token_counter=default_token_heuristic)
    assert result != ""
    assert default_token_heuristic(result) <= 5


# ---------------------------------------------------------------------------
# Budget exceeded — truly irreducible
# ---------------------------------------------------------------------------


def test_yaml_raises_only_when_empty_structure_exceeds_budget(strategy):
    """Raise only when even an empty {} structure cannot fit in budget.

    The default heuristic (len // 4) gives 0 tokens for '{}\\n', so a custom
    counter that charges ≥1 for any input is needed to exercise the raise path.
    """
    content = "key: value\n"
    with pytest.raises(ContextBudgetExceededError):
        strategy.compress(content, budget=0, token_counter=lambda _: 1)


def test_yaml_barely_within_budget_does_not_raise(strategy):
    content = "k: v\n"
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
