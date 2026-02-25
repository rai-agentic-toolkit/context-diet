"""
Python Abstract Syntax Tree (AST) deterministic compressor.
"""

from typing import Any

import libcst as cst

from ..interfaces import ContextBudgetExceededError, DietStrategy, TokenCounter


class _ScrubSkeletonTransformer(cst.CSTTransformer):
    """
    LibCST Transformer to safely strip docstrings and optionally skeletonize bodies
    without losing inline comments or fundamental format structure.
    """

    def __init__(self, skeletonize: bool = False, focus_on: str | None = None):
        self.skeletonize = skeletonize
        self.focus_on = focus_on

    def _strip_docstring(self, body_sequence):
        """Removes the first statement if it is a string literal (docstring)."""
        if not body_sequence:
            return body_sequence

        first = body_sequence[0]
        # Check if the first statement is a simple string expression (docstring)
        if isinstance(first, cst.SimpleStatementLine) and len(first.body) == 1:
            expr = first.body[0]
            if isinstance(expr, cst.Expr) and isinstance(expr.value, cst.SimpleString):
                return body_sequence[1:]
        return body_sequence

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        new_body = self._strip_docstring(updated_node.body)
        return updated_node.with_changes(body=new_body)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        new_body = updated_node.body.with_changes(
            body=self._strip_docstring(updated_node.body.body)
        )
        return updated_node.with_changes(body=new_body)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        if self.skeletonize:
            # We don't focus-target in the current naive framework unless requested
            # Simply replace body with `...`
            ellipsis_stmt = cst.SimpleStatementLine(body=[cst.Expr(value=cst.Ellipsis())])
            new_body = updated_node.body.with_changes(body=[ellipsis_stmt])
            return updated_node.with_changes(body=new_body)
        else:
            new_body = updated_node.body.with_changes(
                body=self._strip_docstring(updated_node.body.body)
            )
            return updated_node.with_changes(body=new_body)

    def leave_AsyncFunctionDef(
        self, original_node: cst.AsyncFunctionDef, updated_node: cst.AsyncFunctionDef
    ) -> cst.AsyncFunctionDef:
        if self.skeletonize:
            ellipsis_stmt = cst.SimpleStatementLine(body=[cst.Expr(value=cst.Ellipsis())])
            new_body = updated_node.body.with_changes(body=[ellipsis_stmt])
            return updated_node.with_changes(body=new_body)
        else:
            new_body = updated_node.body.with_changes(
                body=self._strip_docstring(updated_node.body.body)
            )
            return updated_node.with_changes(body=new_body)


class PythonAstDietStrategy(DietStrategy):
    """
    Deterministically transforms Python source code into a structurally precise,
    compressed format utilizing LibCST to retain inline comments.
    """

    def compress(
        self, content: str, budget: int, token_counter: TokenCounter, **kwargs: Any
    ) -> str:
        """
        Calculates and iteratively applies scrub and skeleton logic to satisfy the budget.
        """
        focus_on = kwargs.get("focus_on")
        try:
            tree = cst.parse_module(content)
        except cst.ParserSyntaxError:
            raise ContextBudgetExceededError("SyntaxError: content is not valid Python.")

        # Pass 1: "Scrub Mode" - Remove all docstrings/metadata
        scrub_transformer = _ScrubSkeletonTransformer(skeletonize=False, focus_on=focus_on)
        tree_scrubbed = tree.visit(scrub_transformer)
        scrubbed_content = tree_scrubbed.code

        if token_counter(scrubbed_content) <= budget:
            return scrubbed_content

        # Pass 2: "Skeleton Mode" - Aggressively prune implementation details
        skeleton_transformer = _ScrubSkeletonTransformer(skeletonize=True, focus_on=focus_on)
        tree_skeleton = tree.visit(skeleton_transformer)
        skeleton_content = tree_skeleton.code

        # If even the skeleton exceeds the budget (massive files), throw an error.
        if token_counter(skeleton_content) > budget:
            raise ContextBudgetExceededError(
                f"Minimum Python skeleton exceeds budget ({budget} tokens)."
            )

        return skeleton_content
