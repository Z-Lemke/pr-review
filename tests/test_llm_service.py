import pytest
from unittest.mock import patch, MagicMock
import json
import sys
from src.services.llm_service import LLMService
from src.models.pr_models import GuidelinesInfo, DocumentInfo


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

    def test_analyze_diff_with_context_success(self):
        """Test analyze_diff_with_context method with successful response."""
        mock_issues = [
            {
                "line": 10,
                "description": "Test issue with context",
                "severity": "high",
                "suggestion": "Fix it with context",
                "guideline_violation": "Follow PEP8"
            }
        ]
        
        mock_response = f"```json\n{json.dumps(mock_issues)}\n```"
        
        # Create mock guidelines and docs
        mock_guidelines = GuidelinesInfo(
            content="# Guidelines\n- Follow PEP8\n- Write tests",
            source="CONTRIBUTING.md",
            parsed_rules=["Follow PEP8", "Write tests"]
        )
        
        mock_docs = [
            DocumentInfo(
                path="README.md",
                content="# Test Project\nThis is a test.",
                type="README"
            )
        ]
        
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
            result = service.analyze_diff_with_context(
                file_path="test_file.py",
                diff_content="test diff content",
                full_file_content="def test():\n    pass",
                guidelines=mock_guidelines,
                repository_docs=mock_docs
            )
            
            # Check that the result matches the expected structure
            assert len(result) == len(mock_issues)
            assert result[0]["line"] == mock_issues[0]["line"]
            assert result[0]["description"] == mock_issues[0]["description"]
            assert result[0]["severity"] == mock_issues[0]["severity"]
            assert result[0]["suggestion"] == mock_issues[0]["suggestion"]
            assert result[0]["guideline_violation"] == mock_issues[0]["guideline_violation"]
            
            # Verify the chain was invoked with the right arguments
            mock_chain.invoke.assert_called_once()
            call_args = mock_chain.invoke.call_args[0][0]
            assert "test_file.py" in str(call_args)
            assert "test diff content" in str(call_args)
            assert "def test():" in str(call_args)
            assert "Follow PEP8" in str(call_args)
            assert "Test Project" in str(call_args)

    def test_analyze_diff_with_context_invalid_json(self):
        """Test analyze_diff_with_context method with invalid JSON response."""
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
            result = service.analyze_diff_with_context(
                file_path="test_file.py",
                diff_content="test diff content",
                full_file_content="def test():\n    pass"
            )
            
            # Verify that we get a fallback response for invalid JSON
            assert len(result) == 1
            assert "Failed to parse response" in result[0]["suggestion"]
            assert result[0]["file_path"] == "test_file.py"
            assert result[0]["line"] == 1
            
            mock_chain.invoke.assert_called_once()

    def test_analyze_pr_description_success(self):
        """Test analyze_pr_description method with successful response."""
        mock_analysis = {
            "summary": "This PR adds a new feature",
            "key_changes": ["Added new function", "Fixed bug"],
            "potential_issues": ["Might need more tests"],
            "suggested_focus_areas": ["Test coverage", "Documentation"]
        }
        
        mock_response = f"```json\n{json.dumps(mock_analysis)}\n```"
        
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
            result = service.analyze_pr_description(
                title="Add new feature",
                description="This PR adds a new feature and fixes a bug",
                repository_docs=[
                    DocumentInfo(
                        path="README.md",
                        content="# Test Project\nThis is a test.",
                        type="README"
                    )
                ]
            )
            
            # Check that the result matches the expected structure
            assert result["summary"] == mock_analysis["summary"]
            assert result["key_changes"] == mock_analysis["key_changes"]
            assert result["potential_issues"] == mock_analysis["potential_issues"]
            assert result["suggested_focus_areas"] == mock_analysis["suggested_focus_areas"]
            
            # Verify the chain was invoked with the right arguments
            mock_chain.invoke.assert_called_once()
            call_args = mock_chain.invoke.call_args[0][0]
            assert "Add new feature" in str(call_args)
            assert "adds a new feature and fixes a bug" in str(call_args)
            assert "Test Project" in str(call_args)

    def test_analyze_pr_description_invalid_json(self):
        """Test analyze_pr_description method with invalid JSON response."""
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
            result = service.analyze_pr_description(
                title="Add new feature",
                description="This PR adds a new feature"
            )
            
            # Verify that we get a fallback response for invalid JSON
            assert "error" in result
            assert "Failed to parse response" in result["error"]
            assert "summary" in result
            assert "Could not analyze PR description" in result["summary"]
            
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

    def test_extract_json_from_response_with_code_block(self):
        """Test _extract_json_from_response method with code block."""
        mock_data = {"key": "value"}
        mock_response = f"Some text\n```json\n{json.dumps(mock_data)}\n```\nMore text"
        
        service = LLMService()
        result = service._extract_json_from_response(mock_response)
        
        assert result == mock_data

    def test_extract_json_from_response_without_code_block(self):
        """Test _extract_json_from_response method without code block."""
        mock_data = {"key": "value"}
        mock_response = json.dumps(mock_data)
        
        service = LLMService()
        result = service._extract_json_from_response(mock_response)
        
        assert result == mock_data

    def test_extract_json_from_response_invalid_json(self):
        """Test _extract_json_from_response method with invalid JSON."""
        mock_response = "This is not valid JSON"
        
        service = LLMService()
        with pytest.raises(json.JSONDecodeError):
            service._extract_json_from_response(mock_response)
