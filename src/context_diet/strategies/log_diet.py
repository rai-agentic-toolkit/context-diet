import re
from collections.abc import Callable
from typing import Any

from context_diet.interfaces import DietStrategy


class LogDietStrategy(DietStrategy):
    """
    Compresses application logs by maintaining the continuity of multi-line Python stack traces
    and aggressively stripping non-UTF-8 binary pollution to protect terminal endpoints.
    """

    def compress(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        # Phase 1: Binary / UTF-8 safety stripping
        # Standardize to utf-8 string, dropping any corrupted byte pollution natively
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        else:
            # We encode and decode to force stripping of surrogate characters or anomalies
            content = content.encode("utf-8", errors="ignore").decode("utf-8")

        # Re-enforce budget after the raw string is memory safe
        if token_counter(content) <= budget:
            return content

        # Phase 2: Error-Grep Mode using PCRE Lookaheads
        # Group log clusters using standard timestamp headers (YYYY-MM-DD or standard syslog format)
        # We split by looking AHEAD for a line that starts with a timestamp or log level

        # Regex explanation:
        # \n(?=...) matches a newline ONLY IF what follows is:
        # 1. A date format like 2024-01-01 or 24/01/01
        # 2. A standard log level like INFO, ERROR, WARN, DEBUG
        # 3. An ISO8601 timestamp [2024-
        split_pattern = re.compile(
            r"\n(?=\d{2,4}[-/]\d{2}[-/]\d{2}|\[?\d{4}-\d{2}-\d{2}|(?:INFO|ERROR|WARN|DEBUG|CRITICAL)\b|\[)",
            re.IGNORECASE,
        )

        # We don't want to split if the file is just one giant block of text that doesn't look like logs
        # So if we don't find any log headers, we just fall back immediately
        log_blocks = split_pattern.split(content)

        if len(log_blocks) <= 1:
            from context_diet.strategies.plain_text import PlainTextDietStrategy

            return PlainTextDietStrategy().compress(content, budget, token_counter, **kwargs)

        # Compile specific high-value blocks (Errors/Exceptions) first
        high_value_blocks = []
        regular_blocks = []

        for block in log_blocks:
            if re.search(
                r"(Traceback \(most recent call last\):|Error:|Exception:|[Ff]atal)", block
            ):
                high_value_blocks.append(block)
            else:
                regular_blocks.append(block)

        output = ""
        tokens_used = 0

        # Priorities: Inject errors first, then pad with regular context if budget allows
        # This guarantees that the stack trace is not truncated or lost by 'tail -n' approximations
        for block in high_value_blocks + regular_blocks:
            item_tokens = token_counter(block) + 1  # +1 for newline injection

            if tokens_used + item_tokens > budget:
                if tokens_used == 0:
                    # Not even the first error fits
                    from context_diet.interfaces import ContextBudgetExceededError

                    raise ContextBudgetExceededError(
                        "Single log block exceeds total token budget."
                    )
                break

            output += block + "\n"
            tokens_used += item_tokens

        return output.strip()
