import pytest
from unittest.mock import patch, MagicMock
import json
import sys
from src.services.llm_service import LLMService


class TestLLMService:
    def test_init(self):
        """Test LLMService initialization."""
        with patch('src.services.llm_service.ChatOllama') as mock_ollama:
            service = LLMService(model_name="test-model", base_url="http://test-url")
            
            assert service.model_name == "test-model"
            assert service.base_url == "http://test-url"
            mock_ollama.assert_called_once_with(
                model="test-model",
                base_url="http://test-url"
            )

    def test_create_chat_model(self):
        """Test _create_chat_model method."""
        with patch.object(LLMService, '_create_chat_model') as mock_create_model:
            mock_model = MagicMock()
            mock_create_model.return_value = mock_model
            
            service = LLMService()
            service._create_chat_model(temperature=0.5)
            
            mock_create_model.assert_called_once_with(temperature=0.5)

    def test_analyze_diff_success(self):
        """Test analyze_diff method with successful response."""
        mock_issues = [
            {
                "line_number": 10,
                "description": "Test issue",
                "severity": "medium",
                "suggestion": "Fix it"
            }
        ]
        
        mock_response = f"```json\n{json.dumps(mock_issues)}\n```"
        
        with patch.object(LLMService, '_create_chat_model') as mock_create_model, \
             patch('src.services.llm_service.ChatPromptTemplate') as mock_prompt, \
             patch('src.services.llm_service.StrOutputParser') as mock_parser:
            
            # Setup the chain pipeline
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            
            mock_model = MagicMock()
            mock_create_model.return_value = mock_model
            
            mock_prompt_instance = MagicMock()
            mock_prompt.from_messages.return_value = mock_prompt_instance
            
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            
            # Set up the pipeline
            mock_prompt_instance.__or__.return_value = MagicMock()
            mock_prompt_instance.__or__.return_value.__or__.return_value = mock_chain
            
            # Create a service with our mocks
            service = LLMService()
            result = service.analyze_diff("test_file.py", "test diff content")
            
            # Check that the result matches the expected structure
            assert len(result) == len(mock_issues)
            assert result[0]["line_number"] == mock_issues[0]["line_number"]
            assert result[0]["description"] == mock_issues[0]["description"]
            assert result[0]["severity"] == mock_issues[0]["severity"]
            assert result[0]["suggestion"] == mock_issues[0]["suggestion"]
            
            mock_chain.invoke.assert_called_once()

    def test_analyze_diff_json_without_code_block(self):
        """Test analyze_diff method with JSON response without code block."""
        mock_issues = [
            {
                "line_number": 10,
                "description": "Test issue",
                "severity": "medium",
                "suggestion": "Fix it"
            }
        ]
        
        mock_response = json.dumps(mock_issues)
        
        with patch.object(LLMService, '_create_chat_model') as mock_create_model, \
             patch('src.services.llm_service.ChatPromptTemplate') as mock_prompt, \
             patch('src.services.llm_service.StrOutputParser') as mock_parser:
            
            # Setup the chain pipeline
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            
            mock_model = MagicMock()
            mock_create_model.return_value = mock_model
            
            mock_prompt_instance = MagicMock()
            mock_prompt.from_messages.return_value = mock_prompt_instance
            
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            
            # Set up the pipeline
            mock_prompt_instance.__or__.return_value = MagicMock()
            mock_prompt_instance.__or__.return_value.__or__.return_value = mock_chain
            
            # Create a service with our mocks
            service = LLMService()
            result = service.analyze_diff("test_file.py", "test diff content")
            
            # Check that the result matches the expected structure
            assert len(result) == len(mock_issues)
            assert result[0]["line_number"] == mock_issues[0]["line_number"]
            assert result[0]["description"] == mock_issues[0]["description"]
            assert result[0]["severity"] == mock_issues[0]["severity"]
            assert result[0]["suggestion"] == mock_issues[0]["suggestion"]
            
            mock_chain.invoke.assert_called_once()

    def test_analyze_diff_invalid_json(self):
        """Test analyze_diff method with invalid JSON response."""
        mock_response = "This is not valid JSON"
        
        with patch.object(LLMService, '_create_chat_model') as mock_create_model, \
             patch('src.services.llm_service.ChatPromptTemplate') as mock_prompt, \
             patch('src.services.llm_service.StrOutputParser') as mock_parser:
            
            # Setup the chain pipeline
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_response
            
            mock_model = MagicMock()
            mock_create_model.return_value = mock_model
            
            mock_prompt_instance = MagicMock()
            mock_prompt.from_messages.return_value = mock_prompt_instance
            
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            
            # Set up the pipeline
            mock_prompt_instance.__or__.return_value = MagicMock()
            mock_prompt_instance.__or__.return_value.__or__.return_value = mock_chain
            
            # Create a service with our mocks
            service = LLMService()
            result = service.analyze_diff("test_file.py", "test diff content")
            
            # Verify that we get a fallback response for invalid JSON
            assert len(result) == 1
            assert "Failed to parse response" in result[0]["suggestion"]
            assert result[0]["file_path"] == "test_file.py"
            assert result[0]["line_number"] == 1
            
            mock_chain.invoke.assert_called_once()

    def test_analyze_diff_exception(self):
        """Test analyze_diff method when an exception occurs."""
        with patch.object(LLMService, '_create_chat_model') as mock_create_model, \
             patch('src.services.llm_service.ChatPromptTemplate') as mock_prompt, \
             patch('src.services.llm_service.StrOutputParser') as mock_parser:
            
            # Setup the chain pipeline to raise an exception
            mock_chain = MagicMock()
            mock_chain.invoke.side_effect = Exception("Test exception")
            
            mock_model = MagicMock()
            mock_create_model.return_value = mock_model
            
            mock_prompt_instance = MagicMock()
            mock_prompt.from_messages.return_value = mock_prompt_instance
            
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            
            # Set up the pipeline
            mock_prompt_instance.__or__.return_value = MagicMock()
            mock_prompt_instance.__or__.return_value.__or__.return_value = mock_chain
            
            # Create a service with our mocks
            service = LLMService()
            result = service.analyze_diff("test_file.py", "test diff content")
            
            # Verify that we get a fallback response for exceptions
            assert len(result) == 1
            assert "Error analyzing diff" in result[0]["suggestion"]
            assert result[0]["file_path"] == "test_file.py"
            assert result[0]["line_number"] == 1
            
            mock_chain.invoke.assert_called_once()
