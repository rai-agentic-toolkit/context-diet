"""
Extended coverage for JsonDietStrategy: empty inputs, tombstone markers,
object depth pruning, and malformed JSON handling.
"""

import json

import pytest

from context_diet.interfaces import ContextBudgetExceededError
from context_diet.strategies.json_diet import JsonDietStrategy
from context_diet.token_utils import default_token_heuristic


@pytest.fixture()
def strategy():
    return JsonDietStrategy()


# ---------------------------------------------------------------------------
# Pass-through / within-budget
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty(strategy):
    assert strategy.compress("", budget=100, token_counter=default_token_heuristic) == ""


def test_whitespace_only_returns_empty(strategy):
    assert strategy.compress("   \n", budget=100, token_counter=default_token_heuristic) == ""


def test_content_within_budget_returned_as_is(strategy):
    content = '{"x": 1}'
    result = strategy.compress(content, budget=10_000, token_counter=default_token_heuristic)
    assert json.loads(result) == {"x": 1}


def test_empty_array_within_budget(strategy):
    result = strategy.compress("[]", budget=100, token_counter=default_token_heuristic)
    assert result == "[]"


def test_empty_object_within_budget(strategy):
    result = strategy.compress("{}", budget=100, token_counter=default_token_heuristic)
    assert result == "{}"


# ---------------------------------------------------------------------------
# Array streaming and truncation
# ---------------------------------------------------------------------------


def test_array_truncation_produces_valid_json(strategy):
    data = [{"id": i, "val": "x" * 20} for i in range(100)]
    content = json.dumps(data)
    result = strategy.compress(content, budget=50, token_counter=default_token_heuristic)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) < 100


def test_array_truncation_tombstone_marker(strategy):
    """When the array is truncated, a __context_diet_warning__ tombstone is injected."""
    data = [{"id": i, "val": "x" * 20} for i in range(100)]
    content = json.dumps(data)
    result = strategy.compress(content, budget=50, token_counter=default_token_heuristic)
    # The tombstone is the last dict in the list
    parsed = json.loads(result)
    last_item = parsed[-1]
    assert "__context_diet_warning__" in last_item
    assert last_item["__context_diet_warning__"] == "TRUNCATED"


def test_array_truncation_preserves_prefix_order(strategy):
    """The first N items must appear in original insertion order."""
    data = [{"id": i} for i in range(50)]
    content = json.dumps(data)
    result = strategy.compress(content, budget=30, token_counter=default_token_heuristic)
    parsed = json.loads(result)
    # Filter out the tombstone
    items = [p for p in parsed if "id" in p]
    for i, item in enumerate(items):
        assert item["id"] == i


def test_single_item_array_always_included(strategy):
    """Even if the single item exceeds budget, the first item is always kept (first_item logic)."""
    data = [{"id": 0}]
    content = json.dumps(data)
    result = strategy.compress(content, budget=1, token_counter=default_token_heuristic)
    parsed = json.loads(result)
    assert parsed[0]["id"] == 0


def test_array_output_always_ends_with_bracket(strategy):
    data = [{"id": i} for i in range(20)]
    content = json.dumps(data)
    result = strategy.compress(content, budget=20, token_counter=default_token_heuristic)
    assert result.endswith("]")


# ---------------------------------------------------------------------------
# Object (dict) depth pruning
# ---------------------------------------------------------------------------


def test_dict_depth_pruning_shallow_keys_preserved(strategy):
    data = {
        "shallow": "value",
        "deep": {"l2": {"l3": {"l4": "buried"}}},
    }
    content = json.dumps(data)
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    parsed = json.loads(result)
    assert "shallow" in parsed
    assert "buried" not in json.dumps(parsed)


def test_dict_depth_pruning_collapses_to_empty_dict(strategy):
    """A flat dict with an oversized value is depth-pruned to {} at max_depth=0."""
    data = {"k": "v" * 1000}
    content = json.dumps(data)
    # At depth 0 the dict collapses to {} which is 0 tokens (fits any budget)
    result = strategy.compress(content, budget=1, token_counter=default_token_heuristic)
    assert json.loads(result) == {}


# ---------------------------------------------------------------------------
# Malformed JSON
# ---------------------------------------------------------------------------


def test_malformed_array_raises(strategy):
    # "[{missing: quote}]" = 4 tokens; budget=3 forces actual parsing
    content = "[{missing: quote}]"
    with pytest.raises(ContextBudgetExceededError, match="Malformed JSON array"):
        strategy.compress(content, budget=3, token_counter=default_token_heuristic)


def test_malformed_object_raises(strategy):
    # '{"unclosed": ' = 3 tokens; budget=2 forces actual parsing
    content = '{"unclosed": '
    with pytest.raises(ContextBudgetExceededError, match="Malformed JSON object"):
        strategy.compress(content, budget=2, token_counter=default_token_heuristic)
