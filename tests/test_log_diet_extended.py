"""
Extended coverage for LogDietStrategy: pass-through, no-structure fallback,
priority ordering, and single-block-too-large error.
"""

import pytest

from context_diet.interfaces import ContextBudgetExceededError
from context_diet.strategies.log_diet import LogDietStrategy
from context_diet.token_utils import default_token_heuristic


@pytest.fixture()
def strategy():
    return LogDietStrategy()


# ---------------------------------------------------------------------------
# Pass-through when content fits budget
# ---------------------------------------------------------------------------


def test_content_within_budget_returned_unchanged(strategy):
    content = "2024-01-01 INFO Everything is fine\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "Everything is fine" in result


# ---------------------------------------------------------------------------
# No log structure — plain text fallback
# ---------------------------------------------------------------------------


def test_no_log_structure_falls_back_to_plaintext(strategy):
    """Content with no recognizable log headers falls through to PlainTextDietStrategy."""
    content = "This is a plain paragraph. " * 200  # ~800 tokens
    result = strategy.compress(content, budget=20, token_counter=default_token_heuristic)
    # PlainText does a budget-respecting slice
    assert default_token_heuristic(result) <= 20


def test_single_block_no_timestamps_falls_back(strategy):
    """A single block of text with no timestamp/level markers triggers the fallback path."""
    content = "Lorem ipsum dolor sit amet. " * 100
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    assert default_token_heuristic(result) <= 10


# ---------------------------------------------------------------------------
# Error block prioritization
# ---------------------------------------------------------------------------


def test_error_blocks_prioritized_over_info(strategy):
    content = (
        "2024-01-01 INFO step A\n"
        "2024-01-01 INFO step B\n"
        "2024-01-01 INFO step C\n"
        "2024-01-01 ERROR Something went wrong\nTraceback (most recent call last):\n  File 'a.py', line 1\nValueError: bad\n"
    )
    # Budget tight enough to force selection
    result = strategy.compress(content, budget=30, token_counter=default_token_heuristic)
    assert "ERROR" in result or "Traceback" in result or "ValueError" in result


def test_multiple_error_blocks_included_in_priority(strategy):
    content = (
        "2024-01-01 ERROR First failure\nTraceback:\nRuntimeError: one\n"
        "2024-01-01 INFO regular log line\n"
        "2024-01-01 ERROR Second failure\nTraceback:\nValueError: two\n"
    )
    result = strategy.compress(content, budget=200, token_counter=default_token_heuristic)
    # Both error blocks should fit at this budget
    assert "RuntimeError" in result
    assert "ValueError" in result


def test_regular_logs_fill_remaining_budget(strategy):
    """Regular log lines are included after error blocks if budget permits."""
    content = (
        "2024-01-01 ERROR Critical failure\nTraceback:\nRuntimeError\n"
        "2024-01-01 INFO Server started on port 8080\n"
    )
    result = strategy.compress(content, budget=200, token_counter=default_token_heuristic)
    assert "Server started" in result


# ---------------------------------------------------------------------------
# Single block too large — budget exceeded
# ---------------------------------------------------------------------------


def test_single_oversized_error_block_raises(strategy):
    """If even the highest-priority block exceeds the budget, raise ContextBudgetExceededError."""
    # Multiple log blocks so we enter the block-priority path (not the plain-text fallback).
    # The error block is huge — guaranteed to exceed budget=1.
    big_error_block = (
        "  File 'x.py', line 1, in func\n    raise RuntimeError('boom')\n" * 30
        + "RuntimeError: too big\n"
    )
    content = (
        "2024-01-01 INFO start\n"
        "2024-01-01 ERROR Fatal\nTraceback (most recent call last):\n"
        + big_error_block
        + "2024-01-01 INFO done\n"
    )
    with pytest.raises(ContextBudgetExceededError, match="Single log block exceeds"):
        strategy.compress(content, budget=1, token_counter=default_token_heuristic)


# ---------------------------------------------------------------------------
# UTF-8 / bytes safety
# ---------------------------------------------------------------------------


def test_string_input_with_surrogates_cleaned(strategy):
    """Surrogate characters are silently dropped during UTF-8 safety pass."""
    # \ud800 is an unpaired surrogate — encode with surrogatepass then hand in as str
    content = "2024-01-01 INFO ok\n\ud800\n2024-01-01 DEBUG done\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "INFO ok" in result
    assert isinstance(result, str)
