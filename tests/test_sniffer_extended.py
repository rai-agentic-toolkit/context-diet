"""
Extended coverage for the content sniffer: extension-based dispatch,
heuristic detection edge cases, and priority ordering.
"""

import pytest

from context_diet.sniffer import detect_strategy


# ---------------------------------------------------------------------------
# Extension-based deterministic dispatch
# ---------------------------------------------------------------------------


def test_extension_map_py():
    assert detect_strategy("", extension=".py") == "python"


def test_extension_map_json():
    assert detect_strategy("", extension=".json") == "json"


def test_extension_map_sql():
    assert detect_strategy("", extension=".sql") == "sql"


def test_extension_map_yml():
    assert detect_strategy("", extension=".yml") == "yaml"


def test_extension_map_yaml():
    assert detect_strategy("", extension=".yaml") == "yaml"


def test_extension_map_txt():
    assert detect_strategy("", extension=".txt") == "text"


def test_extension_map_md():
    assert detect_strategy("", extension=".md") == "text"


def test_extension_map_log():
    assert detect_strategy("", extension=".log") == "log"


def test_extension_map_csv():
    assert detect_strategy("", extension=".csv") == "text"


def test_filename_overrides_heuristic():
    """A .py filename wins over JSON-looking content."""
    json_looking = '{"key": "value"}'
    assert detect_strategy(json_looking, filename="script.py") == "python"


def test_unknown_extension_falls_through_to_heuristic():
    """An unknown extension falls through to structural sniffing."""
    # Content that looks like JSON
    assert detect_strategy('{"a": 1}', extension=".xyz") == "json"


def test_no_extension_on_filename():
    """A filename with no extension falls through to structural sniffing."""
    assert detect_strategy("SELECT 1;", filename="Makefile") == "sql"


# ---------------------------------------------------------------------------
# Heuristic detection — Python
# ---------------------------------------------------------------------------


def test_detects_python_from_import():
    assert detect_strategy("from os import path\n") == "python"


def test_detects_python_class():
    assert detect_strategy("class Foo:\n    pass") == "python"


def test_detects_python_def_multiline():
    content = "\n\ndef greet(name):\n    return f'Hello {name}'"
    assert detect_strategy(content) == "python"


# ---------------------------------------------------------------------------
# Heuristic detection — SQL
# ---------------------------------------------------------------------------


def test_detects_sql_insert():
    assert detect_strategy("INSERT INTO t VALUES (1);") == "sql"


def test_detects_sql_case_insensitive():
    assert detect_strategy("select * from users;") == "sql"


def test_detects_sql_create_table():
    assert detect_strategy("CREATE TABLE foo (id INT);") == "sql"


def test_detects_sql_alter_table():
    assert detect_strategy("ALTER TABLE foo ADD COLUMN bar TEXT;") == "sql"


# ---------------------------------------------------------------------------
# Heuristic detection — Log
# ---------------------------------------------------------------------------


def test_detects_log_from_timestamp_yyyy_mm_dd():
    content = "2024-01-15 10:00:00 INFO Server started"
    assert detect_strategy(content) == "log"


def test_detects_log_from_error_level():
    content = "ERROR: connection refused on port 5432"
    assert detect_strategy(content) == "log"


def test_detects_log_from_traceback_keyword():
    content = "Traceback (most recent call last):\n  File 'app.py', line 1"
    assert detect_strategy(content) == "log"


def test_detects_log_from_debug_level():
    content = "DEBUG starting worker thread 4"
    assert detect_strategy(content) == "log"


# ---------------------------------------------------------------------------
# Heuristic detection — YAML
# ---------------------------------------------------------------------------


def test_detects_yaml_key_value():
    assert detect_strategy("host: localhost\nport: 5432") == "yaml"


def test_detects_yaml_nested():
    content = "database:\n  host: localhost\n  port: 5432"
    assert detect_strategy(content) == "yaml"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_whitespace_only_is_text():
    assert detect_strategy("   \n\t\n   ") == "text"


def test_empty_string_is_text():
    assert detect_strategy("") == "text"


def test_plain_prose_is_text():
    content = "The quick brown fox jumps over the lazy dog."
    assert detect_strategy(content) == "text"


def test_json_array_detected():
    assert detect_strategy("[1, 2, 3]") == "json"


def test_extension_wins_over_json_content():
    """When extension=.sql, it wins over JSON-like content."""
    assert detect_strategy('{"a": 1}', extension=".sql") == "sql"
