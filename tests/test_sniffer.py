from context_diet.sniffer import detect_strategy


def test_detects_json():
    assert detect_strategy('{"a": 1}') == "json"
    assert detect_strategy("[\n  1, 2\n]") == "json"


def test_detects_python():
    assert detect_strategy("import os\n") == "python"
    assert detect_strategy("def hello():\n    pass") == "python"
    assert detect_strategy("class User:\n    pass") == "python"


def test_detects_sql():
    assert detect_strategy("SELECT * FROM users;") == "sql"
    assert detect_strategy("  CREATE TABLE test (id int);") == "sql"


def test_detects_yaml():
    assert detect_strategy("server:\n  port: 8080") == "yaml"
    assert detect_strategy('name: "John"\nage: 30') == "yaml"


def test_detects_plain_text():
    assert detect_strategy("Just a normal sentence") == "text"
    assert detect_strategy("") == "text"
