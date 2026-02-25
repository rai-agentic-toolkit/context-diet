import re
from collections.abc import Callable
from typing import Any

from context_diet.interfaces import DietStrategy


class SqlDietStrategy(DietStrategy):
    """
    Compresses SQL by iteratively isolating DDL statements (schemas) while aggressively destroying DML statements (data row dumps).
    Implements a 3-Tier Graceful Degradation architecture described in the ADR.
    """

    def compress(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        # Tier 1: Optimal Execution (Abstract Syntax Tree Generation via sqlglot)
        try:
            return self._parse_ast(content, budget, token_counter, **kwargs)
        except ImportError:
            # sqlglot is an optional extra context-diet[sql]
            pass
        except Exception as e:
            # Trapping any potential parsing failure from the AST module (e.g. unrecognizable dialect)
            import logging

            logger = kwargs.get("logger") or logging.getLogger(__name__)
            logger.debug(f"Tier 1 sqlglot AST parsing failed: {e}. Degrading to Regex Engine.")

        # Tier 2: Degraded Fallback (Regex Pattern Extraction)
        try:
            return self._extract_ddl_regex(content, budget, token_counter, **kwargs)
        except Exception as e:
            import logging

            logger = kwargs.get("logger") or logging.getLogger(__name__)
            logger.warning(
                f"Tier 2 Regex sql parsing failed: {e}. Degrading to blind string slice."
            )

        # Tier 3: Terminal Fallback
        from context_diet.strategies.plain_text import PlainTextDietStrategy

        return PlainTextDietStrategy().compress(content, budget, token_counter, **kwargs)

    def _parse_ast(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        """Tier 1: Constructs a mathematically perfect AST using the optional sqlglot package."""
        import sqlglot
        from sqlglot import exp

        # Parse the SQL into an expression tree, returning a list of valid expressions
        dialect = kwargs.get("dialect", None)
        expressions = sqlglot.parse(content, read=dialect)

        valid_ddl = []
        for e in expressions:
            if not e:
                continue
            # We strictly whitelist schema-definition objects to isolate DDL
            if isinstance(e, (exp.Create, exp.Alter, exp.Drop)):
                valid_ddl.append(e.sql(dialect=dialect))

        # Now we compile the extracted DDl until we hit the budget boundary
        output = ""
        tokens_used = 0

        for statement in valid_ddl:
            # Always ensure the statment ends cleanly
            if not statement.endswith(";"):
                statement += ";"

            item_tokens = token_counter(statement)

            if tokens_used + item_tokens > budget:
                if tokens_used == 0:
                    # Even the first DDL statment breaks the budget. We raise to trigger fallback.
                    from context_diet.interfaces import ContextBudgetExceededError

                    raise ContextBudgetExceededError(
                        "Minimum viable SQL DDL schema exceeds token budget."
                    )
                break

            output += statement + "\n"
            tokens_used += item_tokens

        if not output:
            from context_diet.interfaces import ContextBudgetExceededError

            raise ContextBudgetExceededError(
                "No viable SQL DDL identified in payload during AST Parse."
            )

        return output

    def _extract_ddl_regex(
        self, content: str, budget: int, token_counter: Callable[[str], int], **kwargs: Any
    ) -> str:
        """
        Tier 2: Zero-Dependency Regular Expression extraction.
        Aggressively targets CREATE/ALTER statements and annihilates INSERT/UPDATE tables.
        """

        # Pass 1: Destructive DML Stripping
        # We must use re.DOTALL (re.S) so `.*?` consumes across multi-line insert rows until standard semicolon
        content = re.sub(
            r"(?i)^\s*(INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK)\s+.*?;",
            "",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )

        # Pass 2: DDL Structural Extraction
        ddl_statements = []

        # Find all CREATE statements
        create_pattern = re.compile(
            r"^\s*CREATE\s+(?:TABLE|VIEW|INDEX)\s+([\w\.]+)\s*\(.*?\)\s*;",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        for match in create_pattern.finditer(content):
            ddl_statements.append(match.group(0).strip())

        # Find all ALTER statements (foreign keys)
        alter_pattern = re.compile(
            r"^\s*ALTER\s+(?:TABLE|VIEW)\s+([\w\.]+)\s+.*?;",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        for match in alter_pattern.finditer(content):
            ddl_statements.append(match.group(0).strip())

        if not ddl_statements:
            from context_diet.interfaces import ContextBudgetExceededError

            raise ContextBudgetExceededError("No viable SQL DDL schema detected via Regex.")

        # Pass 3: Budget Reassembly prioritizing CREATE structures
        output = ""
        tokens_used = 0

        # DDL statements from Pass 2 are already natively clustered due to iteration order,
        # so CREATE statements are naturally processed before ALTERs.
        for stmt in ddl_statements:
            item_tokens = token_counter(stmt) + 1  # +1 for newline
            if tokens_used + item_tokens > budget:
                if tokens_used == 0:
                    from context_diet.interfaces import ContextBudgetExceededError

                    raise ContextBudgetExceededError(
                        "Regex extracted schema component exceeds token budget."
                    )
                break
            output += stmt + "\n"
            tokens_used += item_tokens

        return output

    # End of SqlDietStrategy
