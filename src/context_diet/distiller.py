"""
Core orchestration layer for the context-diet framework.
"""

import logging
import warnings
from collections.abc import Callable
from typing import Any

from .interfaces import ContextBudgetExceededError
from .registry import StrategyRegistry
from .sniffer import detect_strategy
from .token_utils import default_token_heuristic


def distill(
    content: str,
    budget: int = 2000,
    strategy: str = "auto",
    token_counter: Callable[[str], int] | None = None,
    filename: str | None = None,
    extension: str | None = None,
    **kwargs: Any,
) -> str:
    """
    Deterministically compresses structural payloads to fit within a token budget.

    Args:
        content: The raw input payload string.
        budget: The strict numerical token limit (default: 2000).
        strategy: The dispatch target directive, defaulting to "auto".
        token_counter: An optional callable to count tokens; defaults to a safe heuristic.
        filename: Optional context filename to bypass regex sniffing.
        extension: Optional explicit file extension to bypass regex sniffing.
        **kwargs: Extension parameters for strategy-specific tuning.

    Returns:
        The structurally compressed string that fits the budget.
    """
    if budget <= 0:
        return ""

    if token_counter is None:
        warnings.warn(
            "Relying on the default default_token_heuristic is dangerous for strict API limits. "
            "Please provide an authentic tokenizer function (like tiktoken) via the `token_counter` argument.",
            RuntimeWarning,
            stacklevel=2,
        )
        token_counter = default_token_heuristic

    auto_detected = False
    if strategy == "auto":
        strategy = detect_strategy(content, filename=filename, extension=extension)
        auto_detected = True

    strategy_class = StrategyRegistry.get_strategy(strategy)
    strategy_instance = strategy_class()

    import json

    import libcst as cst

    try:
        return strategy_instance.compress(content, budget, token_counter, **kwargs)
    except Exception as e:
        raise e
