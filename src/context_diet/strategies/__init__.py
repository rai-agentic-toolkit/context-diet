"""
Export strategies and initialize the StrategyRegistry.
"""

from .json_diet import JsonDietStrategy
from .log_diet import LogDietStrategy
from .plain_text import PlainTextDietStrategy
from .python_ast import PythonAstDietStrategy
from .sql_diet import SqlDietStrategy
from .yaml_diet import YamlDietStrategy
