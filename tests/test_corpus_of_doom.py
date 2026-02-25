import pytest

from context_diet import distill


def test_corpus_nested_json():
    with open("tests/corpus_of_doom/nested.json") as f:
        content = f.read()

    # 10 budget truncates depth heavily
    compressed = distill(content, budget=10)
    assert len(compressed) < len(content)


def test_corpus_unindented_py():
    with open("tests/corpus_of_doom/unindented.py") as f:
        content = f.read()

    from context_diet.interfaces import ContextBudgetExceededError

    with pytest.raises(ContextBudgetExceededError):
        compressed = distill(content, budget=5, strategy="python")
