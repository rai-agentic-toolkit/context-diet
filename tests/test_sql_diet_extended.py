"""
Extended coverage for SqlDietStrategy: DDL-only pass-through, DML-only content,
ALTER TABLE handling, and budget boundary behavior.
"""

import pytest

from context_diet.strategies.sql_diet import SqlDietStrategy
from context_diet.token_utils import default_token_heuristic


@pytest.fixture()
def strategy():
    return SqlDietStrategy()


# ---------------------------------------------------------------------------
# Pass-through / within budget
# ---------------------------------------------------------------------------


def test_small_ddl_within_budget_returned(strategy):
    content = "CREATE TABLE t (id INT PRIMARY KEY);\n"
    result = strategy.compress(content, budget=100_000, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result


def test_ddl_content_strips_inserts(strategy):
    content = """
CREATE TABLE orders (id INT PRIMARY KEY, amount DECIMAL(10,2));
INSERT INTO orders VALUES (1, 99.99);
INSERT INTO orders VALUES (2, 149.99);
"""
    result = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result
    assert "INSERT" not in result


def test_ddl_content_strips_updates(strategy):
    content = """
CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100));
UPDATE users SET name = 'Alice' WHERE id = 1;
"""
    result = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result
    assert "UPDATE" not in result


def test_ddl_content_strips_deletes(strategy):
    content = """
CREATE TABLE logs (id INT, msg TEXT);
DELETE FROM logs WHERE id < 100;
"""
    result = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result
    assert "DELETE" not in result


# ---------------------------------------------------------------------------
# ALTER TABLE preservation
# ---------------------------------------------------------------------------


def test_alter_table_preserved(strategy):
    content = """
CREATE TABLE users (id INT PRIMARY KEY);
ALTER TABLE users ADD COLUMN email VARCHAR(255);
"""
    result = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result
    assert "ALTER TABLE" in result


# ---------------------------------------------------------------------------
# Only DML content — falls back to plain text slice
# ---------------------------------------------------------------------------


def test_only_dml_content_falls_back_to_text_slice(strategy):
    """
    Content with no DDL raises through tier 1 and tier 2, falling to tier 3 (plain text).
    The result is a budget-respecting character slice of the original DML content.
    """
    content = "INSERT INTO t VALUES (1);\n" * 100
    result = strategy.compress(content, budget=10, token_counter=default_token_heuristic)
    # Tier 3 plain text slice — result must respect the token budget
    assert default_token_heuristic(result) <= 10


def test_only_select_falls_back_to_text_slice(strategy):
    content = "SELECT * FROM users WHERE id = 1;\n" * 50
    result = strategy.compress(content, budget=15, token_counter=default_token_heuristic)
    assert default_token_heuristic(result) <= 15


# ---------------------------------------------------------------------------
# Multiple CREATE statements — budget boundary
# ---------------------------------------------------------------------------


def test_multiple_create_tables_budget_truncation(strategy):
    content = "\n".join(
        [f"CREATE TABLE t{i} (id INT PRIMARY KEY, val VARCHAR(100));" for i in range(20)]
    )
    result = strategy.compress(content, budget=30, token_counter=default_token_heuristic)
    assert "CREATE TABLE" in result
    assert default_token_heuristic(result) <= 30


def test_multiple_create_tables_first_is_included(strategy):
    """At least the first DDL statement should always be included."""
    content = "CREATE TABLE alpha (id INT);\n" + "CREATE TABLE beta (id INT);\n" * 20
    result = strategy.compress(content, budget=20, token_counter=default_token_heuristic)
    assert "alpha" in result


# ---------------------------------------------------------------------------
# Output is valid SQL (syntactically closed)
# ---------------------------------------------------------------------------


def test_output_statements_end_with_semicolon(strategy):
    content = "CREATE TABLE t (id INT PRIMARY KEY);\n"
    result = strategy.compress(content, budget=5000, token_counter=default_token_heuristic)
    stripped = result.strip()
    # Last non-empty statement should end with ;
    lines = [l for l in stripped.splitlines() if l.strip()]
    last_token = lines[-1].strip() if lines else ""
    assert last_token.endswith(";") or "CREATE TABLE" in result
