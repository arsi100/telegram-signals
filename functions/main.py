import functions_framework
import logging
import sys

# Minimal logging setup just in case
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True)
logger = logging.getLogger(__name__)

@functions_framework.http
def run_signal_generation(request):
    """Minimal function to test logging."""
    message = "***** MINIMAL FUNCTION EXECUTING *****"
    print(message) # Try basic print
    logger.info(message) # Try logging
    return "Minimal function executed.", 200

# Ensure this is the ONLY content in the file.
