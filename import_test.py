import logging

logging.basicConfig(level=logging.INFO)

try:
    from micro_scalp_engine import logic_engine
    logging.info("Successfully imported logic_engine.")
    # You can try to call a simple function from it if one exists
    # For example, if logic_engine has a function like `get_version()`:
    # logging.info(f"Logic Engine Version: {logic_engine.get_version()}")
except Exception as e:
    logging.error(f"Failed to import logic_engine: {e}", exc_info=True) 