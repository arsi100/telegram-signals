"""
MICRO-SCALP engine package.
"""

# from . import backtester  # Temporarily disabled due to syntax errors
# from . import backtest_visualizer  # Temporarily disabled - requires seaborn
from . import data_ingestion
from . import data_processor
from . import entry_logic
from . import level_finder
from . import logic_engine
from . import position_tracker
from . import pattern_recognition
from . import risk_management
from . import order_execution

__all__ = [
    'data_ingestion',
    'data_processor',
    'logic_engine',
    # 'backtester',  # Temporarily disabled
    # 'backtest_visualizer',  # Temporarily disabled
    'entry_logic',
    'level_finder',
    'position_tracker',
    'pattern_recognition',
    'risk_management',
    'order_execution'
]

"""
Micro Scalping Engine for Cryptocurrency Trading
"""

__version__ = '0.1.0' 