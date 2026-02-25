from context_diet.strategies.sql_diet import SqlDietStrategy
from context_diet.token_utils import default_token_heuristic


def test_sql_diet_extracts_schema():
    strategy = SqlDietStrategy()
    content = """
-- This is a comment
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) /* inline comment */
);

INSERT INTO users (name) VALUES ('Alice'), ('Bob'), ('Charlie');
UPDATE users SET name = 'Dave' WHERE id = 1;
"""
    compressed = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)

    # Verify DDL is kept
    assert "CREATE TABLE users" in compressed
    assert "id SERIAL PRIMARY KEY" in compressed

    # Verify DML is stripped out by Graceful Degradation
    assert "INSERT INTO" not in compressed
    assert "UPDATE users" not in compressed


def test_sql_diet_tier_3_budget_limit():
    strategy = SqlDietStrategy()
    content = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255)
);
"""
    # If the budget is impossibly small, Tier 2 Regex raises an error internally,
    # which is caught by Tier 3 Terminal Fallback that slices strictly to size.
    compressed = strategy.compress(content, budget=10, token_counter=default_token_heuristic)

    # Assert successful compression rather than an unhandled budget error
    assert default_token_heuristic(compressed) <= 10
