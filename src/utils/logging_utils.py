import logging
import sys
from rich.logging import RichHandler

def setup_logging(level=logging.INFO, include_module=False):
    """
    Set up logging with Rich handler for better console output.
    
    Args:
        level: Logging level (default: INFO)
        include_module: Whether to include module name in log messages (default: False)
    
    Returns:
        Logger instance
    """
    # Choose format based on verbosity
    if include_module:
        log_format = "%(levelname)-8s %(name)s:%(lineno)d - %(message)s"
    else:
        log_format = "%(message)s"
    
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=include_module)]
    )
    
    # Get the root logger
    logger = logging.getLogger()
    
    # Set level for all loggers
    logger.setLevel(level)
    
    # Set specific loggers to DEBUG level if in verbose mode
    if level == logging.DEBUG:
        # Set all src.* loggers to DEBUG
        for logger_name in logging.root.manager.loggerDict:
            if logger_name.startswith('src.'):
                logging.getLogger(logger_name).setLevel(logging.DEBUG)
    
    return logger
