import pytest
from unittest.mock import patch, MagicMock
import logging
from src.utils.logging_utils import setup_logging


class TestLoggingUtils:
    def test_setup_logging_default_level(self):
        """Test setup_logging with default level."""
        with patch('logging.basicConfig') as mock_config, \
             patch('logging.getLogger') as mock_get_logger:
            
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            result = setup_logging()
            
            mock_config.assert_called_once()
            mock_get_logger.assert_called_once()
            mock_logger.setLevel.assert_called_once_with(logging.INFO)
            assert result == mock_logger

    def test_setup_logging_custom_level(self):
        """Test setup_logging with custom level."""
        with patch('logging.basicConfig') as mock_config, \
             patch('logging.getLogger') as mock_get_logger:
            
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            result = setup_logging(level=logging.DEBUG)
            
            mock_config.assert_called_once()
            mock_get_logger.assert_called_once()
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
            assert result == mock_logger
