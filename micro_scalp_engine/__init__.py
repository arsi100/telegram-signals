"""
MICRO-SCALP engine package.

This file is intentionally kept minimal. Submodules are imported directly
by the service_wrapper to prevent premature dependency imports that can
crash the container before the HTTP server starts.
"""

# Core services that we need
from . import data_ingestion
from . import data_processor
from . import logic_engine
# Support modules needed by logic_engine
from . import risk_management
from . import order_execution
from . import macro_integration
from . import entry_logic
from . import level_finder
from . import position_tracker
from . import pattern_recognition

# Commented out modules that cause import errors or aren't needed
# from . import backtester  # Temporarily disabled due to syntax errors
# from . import backtest_visualizer  # Temporarily disabled - requires seaborn
# from . import level_finder  # Not needed for current services
# from . import position_tracker  # Not needed for current services
# from . import pattern_recognition  # Not needed for current services

__all__ = [
    'data_ingestion',
    'data_processor',
    'logic_engine',
    'risk_management',
    'order_execution',
    'macro_integration',
    'entry_logic',
    'level_finder',
    'position_tracker',
    'pattern_recognition'
]

"""
Micro Scalping Engine for Cryptocurrency Trading
"""

__version__ = '0.1.0' 