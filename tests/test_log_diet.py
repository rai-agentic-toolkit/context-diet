from context_diet.strategies.log_diet import LogDietStrategy
from context_diet.token_utils import default_token_heuristic


def test_log_diet_extracts_tracebacks():
    strategy = LogDietStrategy()
    content = """
2024-01-01 10:00:00 INFO Application started
2024-01-01 10:00:05 DEBUG Processing request 123
2024-01-01 10:00:06 ERROR Unhandled exception
Traceback (most recent call last):
  File "app.py", line 10, in <module>
    main()
  File "app.py", line 5, in main
    1 / 0
ZeroDivisionError: division by zero
2024-01-01 10:00:10 INFO Application recovering...
"""
    # We set a tight budget so that only the high-value block (Error + Traceback) fits
    compressed = strategy.compress(content, budget=75, token_counter=default_token_heuristic)

    # Verify the traceback is prioritized and kept intact
    assert "Traceback (most recent call last)" in compressed
    assert "ZeroDivisionError: division by zero" in compressed

    # Verify low-value debug logs are dropped due to tight budget
    assert "DEBUG Processing request 123" not in compressed


def test_log_diet_strips_binary_pollution():
    strategy = LogDietStrategy()

    # Injecting invalid UTF-8 bytes to simulate random byte corruption in a log file
    content_with_binary = (
        b"2024-01-01 12:00:00 ERROR Terminal error"
        + b"\xff\xfe\x00\x00"
        + b"\nTraceback:\nValueError\n"
    )

    # The LogDietStrategy should natively strip the invalid \xff\xfe bytes
    compressed = strategy.compress(
        content_with_binary, budget=5000, token_counter=default_token_heuristic
    )

    assert "Terminal error" in compressed
    assert "ValueError" in compressed
    # The output should be a clean string, with the invalid bytes ignored
    assert "\xff\xfe" not in compressed
    assert isinstance(compressed, str)
