import pytest
from unittest.mock import patch, MagicMock
import asyncio
import typer
from typer.testing import CliRunner
from rich.console import Console
import sys
import requests
import subprocess

# Import the app from main
from src.main import app


runner = CliRunner()


class TestMain:
    def test_review_success(self):
        """Test review command with successful execution."""
        with patch('src.main.GitHubService') as mock_gh_service, \
             patch('src.main.LLMService') as mock_llm_service, \
             patch('src.main.PRReviewAgent') as mock_agent_class, \
             patch('src.main.setup_logging') as mock_setup_logging, \
             patch('src.main.asyncio.run') as mock_run, \
             patch('src.main.Console') as mock_console_class:
            
            # Set up mocks
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.analyzed_files = ["file1.py", "file2.py"]
            mock_result.detected_issues = [{"issue": "test"}]
            mock_result.comments_added = [MagicMock(path="file1.py", line=10)]
            
            mock_run.return_value = mock_result
            
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            
            # Call the function
            result = runner.invoke(app, ["review", "123", "--repo", "owner/repo"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mocks were called correctly
            mock_gh_service.assert_called_once_with(repository="owner/repo")
            mock_llm_service.assert_called_once()
            mock_agent_class.assert_called_once()
            mock_run.assert_called_once()

    def test_review_error(self):
        """Test review command when an error occurs."""
        with patch('src.main.GitHubService') as mock_gh_service, \
             patch('src.main.LLMService') as mock_llm_service, \
             patch('src.main.PRReviewAgent') as mock_agent_class, \
             patch('src.main.setup_logging') as mock_setup_logging, \
             patch('src.main.asyncio.run') as mock_run, \
             patch('src.main.Console') as mock_console_class:
            
            # Set up mocks
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            mock_result = MagicMock()
            mock_result.error = "Test error"
            
            mock_run.return_value = mock_result
            
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            
            # Call the function
            result = runner.invoke(app, ["review", "123", "--repo", "owner/repo"])
            
            # Verify the result
            assert result.exit_code == 0

    def test_review_exception(self):
        """Test review command when an exception is raised."""
        with patch('src.main.GitHubService') as mock_gh_service, \
             patch('src.main.LLMService') as mock_llm_service, \
             patch('src.main.PRReviewAgent') as mock_agent_class, \
             patch('src.main.setup_logging') as mock_setup_logging, \
             patch('src.main.asyncio.run') as mock_run, \
             patch('src.main.Console') as mock_console_class:
            
            # Set up mocks
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            
            mock_run.side_effect = Exception("Test exception")
            
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            
            # Call the function
            result = runner.invoke(app, ["review", "123", "--repo", "owner/repo"])
            
            # Verify the result
            assert result.exit_code == 1

    def test_check_ollama_success(self):
        """Test check_ollama command with successful response."""
        with patch('requests.get') as mock_get, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console, \
             patch.dict('sys.modules', {'langchain_ollama': MagicMock()}):
            
            # Set up mocks
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "mistral-openorca"},
                    {"name": "llama2"}
                ]
            }
            mock_get.return_value = mock_response
            
            # Call the function
            result = runner.invoke(app, ["check-ollama"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            mock_get.assert_called_once_with("http://localhost:11434/api/tags")

    def test_check_ollama_no_model(self):
        """Test check_ollama command when model is not available."""
        with patch('requests.get') as mock_get, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console, \
             patch.dict('sys.modules', {'langchain_ollama': MagicMock()}):
            
            # Set up mocks
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama2"}
                ]
            }
            mock_get.return_value = mock_response
            
            # Call the function
            result = runner.invoke(app, ["check-ollama"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            mock_get.assert_called_once_with("http://localhost:11434/api/tags")

    def test_check_ollama_not_running(self):
        """Test check_ollama command when Ollama is not running."""
        with patch('requests.get') as mock_get, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console, \
             patch.dict('sys.modules', {'langchain_ollama': MagicMock()}):
            
            # Set up mocks
            mock_get.side_effect = requests.RequestException("Connection error")
            
            # Call the function
            result = runner.invoke(app, ["check-ollama"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            mock_get.assert_called_once_with("http://localhost:11434/api/tags")

    def test_check_gh_cli_success(self):
        """Test check_gh_cli command with successful response."""
        with patch('subprocess.run') as mock_run, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console:
            
            # Set up mocks
            mock_version_result = MagicMock()
            mock_version_result.returncode = 0
            mock_version_result.stdout = "gh version 2.0.0"
            
            mock_auth_result = MagicMock()
            mock_auth_result.returncode = 0
            
            mock_run.side_effect = [mock_version_result, mock_auth_result]
            
            # Call the function
            result = runner.invoke(app, ["check-gh-cli"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            assert mock_run.call_count == 2

    def test_check_gh_cli_not_installed(self):
        """Test check_gh_cli command when GitHub CLI is not installed."""
        with patch('subprocess.run') as mock_run, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console:
            
            # Set up mocks
            mock_run.side_effect = FileNotFoundError("No such file or directory: 'gh'")
            
            # Call the function
            result = runner.invoke(app, ["check-gh-cli"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            mock_run.assert_called_once()

    def test_check_gh_cli_not_authenticated(self):
        """Test check_gh_cli command when GitHub CLI is not authenticated."""
        with patch('subprocess.run') as mock_run, \
             patch('src.main.Console', return_value=MagicMock()) as mock_console:
            
            # Set up mocks
            mock_version_result = MagicMock()
            mock_version_result.returncode = 0
            mock_version_result.stdout = "gh version 2.0.0"
            
            mock_auth_result = MagicMock()
            mock_auth_result.returncode = 1
            
            mock_run.side_effect = [mock_version_result, mock_auth_result]
            
            # Call the function
            result = runner.invoke(app, ["check-gh-cli"])
            
            # Verify the result
            assert result.exit_code == 0
            
            # Verify the mock was called
            assert mock_run.call_count == 2
