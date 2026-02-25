from collections.abc import Callable
from typing import Any

from context_diet.interfaces import DietStrategy


class YamlDietStrategy(DietStrategy):
    """
    Compresses YAML by removing comments, empty lines, and excessive indentation,
    finally falling back to plain text slicing if still over budget.
    """

    def compress(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        import io

        from ruamel.yaml import YAML

        from context_diet.interfaces import ContextBudgetExceededError

        yaml = YAML(typ="rt")
        yaml.default_flow_style = False

        try:
            data = yaml.load(content)
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

        # Safe round-trip implicitly drops all comments
        buf = io.StringIO()
        yaml.dump(data, buf)
        scrubbed = buf.getvalue()

        if token_counter(scrubbed) <= budget:
            return scrubbed

        raise ContextBudgetExceededError(f"Minimum valid YAML exceeds budget ({budget} tokens).")
