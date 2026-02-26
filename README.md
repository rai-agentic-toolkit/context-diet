# context-diet

**Deterministic syntactic context compression for LLMs.**

`context-diet` is a structural pruning library that understands the syntactic layout of common formats (Python AST, JSON, YAML, SQL) and trims them deterministically to fit within exact LLM token budgets.

## The Problem

When providing context to an LLM, you are strictly bounded by context window token limits. If you have a massive JSON file or a gigantic Python script that needs to fit into an 8,000 token limit, blindly slicing off the tail of the string `payload[:32000]` destroys the structural integrity. JSON arrays lose their closing brackets. Python routines lose their indentation mapping.

`context-diet` ensures that when your context limit expires, the semantic and physical structure of your prompt payload survives.

## Features

- **Structural Parsers:** Understands `.py`, `.json`, `.yml`, `.sql`, and `.log` natively.
- **Python Skeletonization:** Strips docstrings, comments, and eventually skeletonizes method bodies while preserving the AST structural map.
- **JSON Streaming:** Compresses massive JSON arrays object-by-object using pointers to prevent memory trashing.
- **YAML Round-Trip:** Deletes comments while preserving original YAML configuration formatting perfectly.
- **Log Compression:** Maintains multi-line Python stack trace continuity while stripping binary/UTF-8 pollution from application logs.
- **Binary Search Plaintext:** Uses O(log N) slicing for generic text to hit exact budget limits with zero CPU thrashing.

## Installation

```bash
pip install context-diet
```

## Quick Start

```python
from context_diet import distill

my_huge_json = "[{\"id\": 1, ...}]" # 50,000 tokens

# Squashes the array down perfectly to a valid 2,000 token JSON object
safe_json = distill(content=my_huge_json, budget=2000, strategy="json")
```

## Partner Integration: `secure-ingest`

**Important:** `context-diet` solves the token limit constraint equation *after* parsing, but it does not protect your pre-parser intake routines from massive input byte-bombs or semantic prompt injection.

It is highly recommended to wrap `context-diet` extraction pipelines with **[`secure-ingest`](https://github.com/rai-agentic-toolkit/secure-ingest)**. `secure-ingest` can operate immediately at your webhook boundary to reject Zip Bombs and enforce raw `max_size_bytes` limits *before* the structural parsers ever spin up.

```python
from secure_ingest import parse, ContentType
from context_diet import distill

# 1. Reject maliciously huge raw byte payloads at the boundary
safe_bytes_result = parse(
    raw_untrusted_string,
    ContentType.TEXT,
    max_size_bytes=1024 * 1024  # Reject anything over 1MB
)

# 2. Safely squash the trusted structural payload down to the token budget
llm_context = distill(
    safe_bytes_result.content,
    budget=4000,
    strategy="auto",
    filename="config.yml"
)
```

## Security

Please review the `CONSTITUTION.md` for architectural constraints. `context-diet` strictly relies on explicitly vetted non-destructive parsing components.
