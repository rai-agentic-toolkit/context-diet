"""
Core API and strategy interfaces for context-diet.
"""

from typing import Any, Protocol


class TokenCounter(Protocol):
    """
    Protocol for a token counting function.

    Any provided token counter must accept a string and return an integer.
    """

    def __call__(self, text: str) -> int: ...


class DietStrategy:
    """
    Abstract base class for all context compression strategies.

    Every strategy must implement the compress method to deterministically
    reduce a structural payload to fit within the provided token budget.
    """

    def compress(
        self, content: str, budget: int, token_counter: TokenCounter, **kwargs: Any
    ) -> str:
        """
        Compresses the content to fit within the budget.

        Args:
            content: The raw input payload.
            budget: The maximum allowable token limit.
            token_counter: A callable adhering to the TokenCounter protocol.
            **kwargs: Extension parameters for specific strategy implementations.

        Returns:
            The syntactically compressed string.
        """
        raise NotImplementedError("Subclasses must implement compress()")


class ContextBudgetExceededError(Exception):
    """
    Raised when a specialized parsing strategy cannot compress a structural payload
    down to the requested token budget without destroying structural integrity.
    """

    pass
