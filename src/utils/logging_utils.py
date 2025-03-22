import logging
import sys
from rich.logging import RichHandler

def setup_logging(level=logging.INFO):
    """Set up logging with Rich handler for better console output."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    
    # Get the root logger
    logger = logging.getLogger()
    
    # Set level for all loggers
    logger.setLevel(level)
    
    return logger
