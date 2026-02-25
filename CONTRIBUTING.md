# Contributing to context-diet

Thank you for your interest in contributing to `context-diet`!

To guarantee that this framework remains robust, reliable, and deployable in extreme cold-start environments (like edge-compute or AWS Lambda), we strictly enforce a **Zero-Dependency Mandate** for the core library.

Please read the following guidelines carefully before opening a pull request.

---

## The Zero-Dependency Core Mandate

The primary architectural rule of `context-diet` is that the core compression engine (`src/context_diet/`) must operate **exclusively on the Python Standard Library**.

You are highly encouraged to utilize built-in Python modules to solve complex data parsing tasks:
* `ast` (For logic mapping and script transformation)
* `json` (For streaming structured serialization)
* `sqlite3` or `csv` (Instead of bringing in `pandas` or `polars`)
* `argparse` (Instead of bringing in `click` or `typer`)
* `urllib` (Instead of bringing in `requests`)

**Any pull request that introduces an external dependency to the core requirements will be automatically rejected.**

### Why?
We optimize for Token Economics and Deployment Portability over "Probabilistic Smartness". By avoiding heavy machine learning frameworks (`torch`, `transformers`) or data-science libraries (`numpy`), `context-diet` can spin up in microseconds.

---

## Extending the Framework

If you wish to build a compression strategy that absolutely requires a massive external dependency (e.g., parsing a highly complex proprietary file format), you must follow the **Dependency Injection** protocol.

1. **Packaging Extras**: Your external dependency must be marked as optional in `pyproject.toml` (e.g., `[project.optional-dependencies]`).
2. **Graceful Degradation**: Your custom `DietStrategy` plugin must explicitly trap the `ImportError`. If the user did not install the optional package (e.g., `pip install context-diet[myformat]`), your strategy must cleanly degrade to a standard library heuristic (like a Regex fallback) or gracefully raise a `ContextBudgetExceededError`.
3. **No Hardcoded Tokenizers**: Never import specific tokenizers like `tiktoken` into your strategy. You must utilize the generic `token_counter` callable passed down through the `compress()` method.

---

## Development Environment Setup

We utilize modern, PEP-508 compliant dependency management via `pyproject.toml`.

### 1. Initialize an Isolated Environment
Do not install dependencies globally. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Development Dependencies
```bash
pip install -e ".[dev]"
```
*(Optionally, use `pip-tools` to compile requirements via `pip-compile pyproject.toml --extra dev`)*

### 3. Run the Corpus of Doom Matrix
Before sumbitting a PR, you must verify that your changes have not broken the syntactic limits of the existing formats. We run the "Corpus of Doom" across multiple endpoints.

```bash
PYTHONPATH=src pytest tests/
```

### 4. Code Standards
* We use `ruff` for fast linting and formatting. Run `ruff format .` and `ruff check .` before committing.
* Ensure your strategies inherit strictly from `DietStrategy`.
* Add comprehensive docs for any new parameters added to `**kwargs`.

Thank you for helping us keep LLM pipelines stable, fast, and structured!
