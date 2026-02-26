from collections.abc import Callable
from typing import Any

from context_diet.interfaces import DietStrategy


class YamlDietStrategy(DietStrategy):
    """
    Compresses YAML by removing comments, then progressively pruning nested depth
    until the result fits within the token budget.
    """

    def compress(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        import io

        from ruamel.yaml import YAML

        from context_diet.interfaces import ContextBudgetExceededError

        yaml_rt = YAML(typ="rt")
        yaml_rt.default_flow_style = False

        try:
            data = yaml_rt.load(content)
        except Exception:
            raise ContextBudgetExceededError("Malformed YAML cannot be compressed.")

        if data is None:
            return ""

        def remove_comments(node: Any) -> None:
            if hasattr(node, "ca") and node.ca is not None:
                if hasattr(node.ca, "items") and node.ca.items:
                    for k in list(node.ca.items.keys()):
                        del node.ca.items[k]
                if hasattr(node.ca, "comment"):
                    node.ca.comment = None

            if isinstance(node, dict):
                for k, v in node.items():
                    remove_comments(k)
                    remove_comments(v)
            elif isinstance(node, list):
                for item in node:
                    remove_comments(item)

        remove_comments(data)

        buf = io.StringIO()
        yaml_rt.dump(data, buf)
        scrubbed = buf.getvalue()

        if token_counter(scrubbed) <= budget:
            return scrubbed

        # Comment stripping alone wasn't enough. Reload as plain Python objects
        # (no round-trip metadata needed) and progressively prune depth.
        yaml_safe = YAML(typ="safe")
        try:
            plain_data = yaml_safe.load(scrubbed)
        except Exception:
            raise ContextBudgetExceededError("YAML cannot be compressed.")

        yaml_plain = YAML()
        yaml_plain.default_flow_style = False

        for max_depth in range(6, -1, -1):
            pruned = self._mask_deep_nodes(plain_data, max_depth)
            candidate_buf = io.StringIO()
            yaml_plain.dump(pruned, candidate_buf)
            candidate = candidate_buf.getvalue()
            if token_counter(candidate) <= budget:
                return candidate

        raise ContextBudgetExceededError(f"Minimum valid YAML exceeds budget ({budget} tokens).")

    def _mask_deep_nodes(self, node: Any, max_depth: int, current_depth: int = 0) -> Any:
        """Recursively collapse nodes deeper than max_depth into empty structures."""
        if current_depth >= max_depth:
            if isinstance(node, dict):
                return {}
            if isinstance(node, list):
                return []
            if isinstance(node, str):
                return "..."
            return node

        if isinstance(node, dict):
            return {
                k: self._mask_deep_nodes(v, max_depth, current_depth + 1)
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [self._mask_deep_nodes(item, max_depth, current_depth + 1) for item in node]

        return node
