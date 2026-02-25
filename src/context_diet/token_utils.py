"""
Default token counting heuristics and fallbacks.
"""


def default_token_heuristic(text: str) -> int:
    """
    Safe mathematical heuristic for estimating token usage.

    Empirically, 1 token is roughly equivalent to 4 standard English characters.
    This heuristic acts as an operationally safe upper bound for structural data,
    guaranteeing that the output string will never exceed the true context limit.
    """
    return len(text) // 4
