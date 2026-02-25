"""
Fallback plain text compression strategy.
"""

from typing import Any

from ..interfaces import DietStrategy, TokenCounter


class PlainTextDietStrategy(DietStrategy):
    """
    Tier 3 (Terminal Fallback) strategy.

    If no structural signature is recognized, or if structural parsing fails catastrophically,
    this strategy executes a blind, non-structural text slice based on the token budget.
    While structural integrity is not guaranteed, it ensures context limits are preserved.
    """

    def compress(
        self, content: str, budget: int, token_counter: TokenCounter, **kwargs: Any
    ) -> str:
        """
        Slices text strictly respecting the numerical token counter budget.
        """
        if token_counter(content) <= budget:
            return content

        # Binary Search O(log N) for optimal character slice
        low = 0
        high = len(content)
        best_valid_content = ""

        # Early exit optimization for absurdly large files
        estimated_max_chars = budget * 5  # average 4 chars/token + buffer
        if high > estimated_max_chars:
            high = estimated_max_chars

        while low <= high:
            mid = (low + high) // 2
            candidate = content[:mid]

            if token_counter(candidate) <= budget:
                best_valid_content = candidate
                low = mid + 1
            else:
                high = mid - 1

        return best_valid_content
