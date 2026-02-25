"""
Provides the centralized registry for context optimization routines.
"""

from .interfaces import DietStrategy
from .strategies.json_diet import JsonDietStrategy
from .strategies.log_diet import LogDietStrategy
from .strategies.plain_text import PlainTextDietStrategy
from .strategies.python_ast import PythonAstDietStrategy
from .strategies.sql_diet import SqlDietStrategy
from .strategies.yaml_diet import YamlDietStrategy


class StrategyRegistry:
    """
    Central repository for all available compression algorithms.

    Maps string identifiers (e.g., 'json', 'application/json', '.py')
    to their respective DietStrategy classes.
    """

    _registry: Dict[str, Type[DietStrategy]] = {
        "text": PlainTextDietStrategy,
        "python": PythonAstDietStrategy,
        "py": PythonAstDietStrategy,
        "json": JsonDietStrategy,
        "yaml": YamlDietStrategy,
        "yml": YamlDietStrategy,
        "sql": SqlDietStrategy,
        "log": LogDietStrategy,
    }

    @classmethod
    def register(cls, name: str, strategy: Type[DietStrategy]) -> None:
        """
        Registers a specialized strategy with a given string identifier.
        """
        if not issubclass(strategy, DietStrategy):
            raise TypeError(f"Strategy {strategy} must inherit from DietStrategy.")
        cls._registry[name] = strategy

    @classmethod
    def get_strategy(cls, name: str) -> Type[DietStrategy]:
        """
        Retrieves the strategy implementation for the requested identifier.
        """
        strategy = cls._registry.get(name)
        if not strategy:
            raise ValueError(f"No compression strategy registered for '{name}'.")
        return strategy

    @classmethod
    def available_strategies(cls) -> list[str]:
        """Returns a list of all currently registered strategy names."""
        return list(cls._registry.keys())
