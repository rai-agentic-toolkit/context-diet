"""
JSON streaming parser and deterministic truncation strategy.
"""

import json
from typing import Any

from ..interfaces import DietStrategy, TokenCounter


class JsonDietStrategy(DietStrategy):
    """
    Tier 1 Strategy for JSON payloads.

    Utilizes `json.JSONDecoder().raw_decode()` to parse massive arrays object-by-object
    without loading the entire structure into an explosive memory graph. Ensures
    perfect syntactical closure regardless of exactly when the budget expires.
    """

    def compress(
        self, content: str, budget: int, token_counter: TokenCounter, **kwargs: Any
    ) -> str:
        content = content.lstrip()
        if not content:
            return ""

        # Fast path if already within budget
        if token_counter(content) <= budget:
            return content

        # Check if it's an array - Array streaming is our main defense against OOM
        if content.startswith("["):
            return self._stream_and_truncate_array(content, budget, token_counter)

        # Non-array objects (dicts) fall back to dictionary depth pruning
        return self._prune_dictionary_depth(content, budget, token_counter, **kwargs)

    def _stream_and_truncate_array(
        self, content: str, budget: int, token_counter: TokenCounter
    ) -> str:
        """
        Parses a massive JSON array iteratively.
        Maintains O(max(object_size)) space complexity rather than O(array_size).
        Uses pointer arithmetic to prevent O(N^2) memory trashing from string slicing.
        
        Note: This manual state machine is built strictly for standard compliant JSON.
        It explicitly does not support json5, comments, or trailing commas.
        """
        import re

        decoder = json.JSONDecoder()
        WHITESPACE = re.compile(r"[ \t\n\r]*")

        # Find the starting bracket
        idx = content.find("[") + 1

        output = "["
        tokens_used = token_counter("[")
        first_item = True

        while idx < len(content) and tokens_used < budget:
            # Skip whitespace
            match = WHITESPACE.match(content, idx)
            if match:
                idx = match.end()

            if idx >= len(content):
                break

            if content[idx] == "]":
                output += "]"
                break

            if content[idx] == ",":
                idx += 1
                # Skip whitespace after comma
                match = WHITESPACE.match(content, idx)
                if match:
                    idx = match.end()
                if idx >= len(content):
                    break

            try:
                # raw_decode extracts ONE valid JSON object and returns the index where it ended
                obj, ending_idx = decoder.raw_decode(content, idx)

                # Reserialize with zero whitespace
                minified_str = json.dumps(obj, separators=(",", ":"))
                item_tokens = token_counter(minified_str)

                if tokens_used + item_tokens > budget and not first_item:
                    # If this single item breaks the budget, we stop the stream entirely right now.
                    # We inject a tombstone warning and the closing bracket to guarantee syntactic validity.
                    tombstone = ', {"__context_diet_warning__": "TRUNCATED"}'
                    output += tombstone
                    output += "]"
                    break

                if not first_item:
                    output += ","
                    tokens_used += token_counter(",")

                output += minified_str
                tokens_used += item_tokens
                first_item = False

                # Advance the pointer
                idx = ending_idx

            except json.JSONDecodeError:
                # If we hit an error here, the literal array is malformed.
                from ..interfaces import ContextBudgetExceededError

                raise ContextBudgetExceededError("Malformed JSON array cannot be compressed.")

        # If we broke out of the loop from reaching the end of the buffer but didn't close it
        if not output.endswith("]"):
            output += "]"

        return output

    def _prune_dictionary_depth(
        self, content: str, budget: int, token_counter: TokenCounter, **kwargs: Any
    ) -> str:
        """
        For a single massive top-level object ({...}), array streaming logic fails.
        We execute depth-based masking instead.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            from ..interfaces import ContextBudgetExceededError

            raise ContextBudgetExceededError("Malformed JSON object cannot be compressed.")

        current_max_depth = kwargs.get("max_depth", 10)
        minified = json.dumps(data, separators=(",", ":"))

        while token_counter(minified) > budget and current_max_depth >= 0:
            pruned_data = self._mask_deep_nodes(data, current_depth=0, max_depth=current_max_depth)
            minified = json.dumps(pruned_data, separators=(",", ":"))
            current_max_depth -= 1

        # Terminal fallback if depth strictly 0 is still too big
        if token_counter(minified) > budget:
            from ..interfaces import ContextBudgetExceededError

            raise ContextBudgetExceededError(
                f"Minimum valid JSON object exceeds budget ({budget} tokens)."
            )

        return minified

    def _mask_deep_nodes(self, node: Any, current_depth: int, max_depth: int) -> Any:
        """
        Recursively replaces nodes that sit deeper than max_depth with empty structures.
        """
        if current_depth >= max_depth:
            # If we hit max depth, return a collapsed version of this node
            if isinstance(node, dict):
                return {}
            elif isinstance(node, list):
                return []
            elif isinstance(node, str):
                return "..."
            elif isinstance(node, (int, float, bool)) or node is None:
                return node
            return "..."

        if isinstance(node, dict):
            return {
                k: self._mask_deep_nodes(v, current_depth + 1, max_depth) for k, v in node.items()
            }

        if isinstance(node, list):
            return [self._mask_deep_nodes(item, current_depth + 1, max_depth) for item in node]

        return node
