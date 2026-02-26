from context_diet.strategies.yaml_diet import YamlDietStrategy
from context_diet.token_utils import default_token_heuristic


def test_yaml_diet_removes_comments():
    strategy = YamlDietStrategy()
    content = """
# This is a comment
server:
  port: 8080 # inline comment
  host: localhost
"""
    compressed = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    assert "# This is a comment" not in compressed
    assert "# inline comment" not in compressed
    assert "server:" in compressed
    assert "port: 8080" in compressed
    assert "host: localhost" in compressed


def test_yaml_diet_budget_limit_prunes_not_raises():
    strategy = YamlDietStrategy()
    content = """
server:
  port: 8080
  host: localhost
  workers: 4
  timeout: 30
"""
    # budget=10 is too small for the full doc but large enough for a pruned skeleton.
    # Should degrade gracefully rather than raise.
    compressed = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    assert compressed != ""
    assert default_token_heuristic(compressed) <= 10
