"""
Unit tests for the JSON Diet Strategy.
"""

import json

from context_diet.strategies.json_diet import JsonDietStrategy
from context_diet.token_utils import default_token_heuristic


def test_json_array_streaming():
    strategy = JsonDietStrategy()

    # Large array of items
    data = [{"id": i, "value": f"item_{i}"} for i in range(100)]
    content = json.dumps(data)

    # We want a budget big enough for ~10 items
    budget = 400
    compressed = strategy.compress(content, budget=budget, token_counter=default_token_heuristic)

    # Should definitely be truncated
    assert len(compressed) < len(content)
    # Should end perfectly syntactically
    assert compressed.endswith("]")

    # Should be valid JSON
    parsed = json.loads(compressed)
    assert isinstance(parsed, list)
    assert len(parsed) < 100
    assert len(parsed) > 0
    assert parsed[0]["id"] == 0


def test_json_depth_limit_object():
    strategy = JsonDietStrategy()

    data = {"level1": {"level2": {"level3": {"level4": "way too deep"}}}, "keep": "this"}
    content = json.dumps(data)

    # Restrict budget so it forces depth collapse
    # "level1" tree alone has about 18 tokens natively.
    compressed = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    parsed = json.loads(compressed)

    assert "keep" in parsed
    # Deep nested objects should turn into empty structs or fall back appropriately
    assert "level1" in parsed

    # Depending on how the depth slices, we just want to ensure we don't have the deepest element.
    # We might have {"level1": {}}, or {"level1": {"level2": {}}} etc.
    str_dump = json.dumps(parsed)
    assert "way too deep" not in str_dump


def test_json_fallback_on_malformed():
    strategy = JsonDietStrategy()

    content = '{"missing_quote: 1, "unclosed_array": ['
    # Very small budget forces trimming
    compressed = strategy.compress(content, budget=10, token_counter=default_token_heuristic)

    # Should fall back to naive string slicing
    assert len(compressed) <= 40  # 10 tokens * 4 chars
