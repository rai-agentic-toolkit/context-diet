"""
context-diet: Deterministic syntactic context compression for LLMs.
"""

import context_diet.strategies

from .distiller import distill

__version__ = "0.1.0"
__all__ = ["distill"]
