import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio
from datetime import datetime

from src.core.pr_review_agent import PRReviewAgent
from src.models.pr_models import PRReviewState, PullRequest, FileChange, PRComment


class TestPRReviewAgent:
    def test_init(self, mock_github_service, mock_llm_service):
        """Test PRReviewAgent initialization."""
        with patch.object(PRReviewAgent, '_build_graph') as mock_build:
            mock_build.return_value = MagicMock()
            
            agent = PRReviewAgent(mock_github_service, mock_llm_service)
            
            assert agent.github_service == mock_github_service
            assert agent.llm_service == mock_llm_service
            mock_build.assert_called_once()

    def test_build_graph(self, mock_github_service, mock_llm_service):
        """Test _build_graph method."""
        # Create a simple mock to verify the method was called
        with patch.object(PRReviewAgent, '_build_graph') as mock_build_graph:
            # Make the mock return a MagicMock for the graph
            mock_graph = MagicMock()
            mock_build_graph.return_value = mock_graph
            
            # Create the agent which will call _build_graph internally
            agent = PRReviewAgent(mock_github_service, mock_llm_service)
            
            # Verify the method was called
            mock_build_graph.assert_called_once()
            
            # Verify the graph was assigned to the agent
            assert agent.graph == mock_graph

    @pytest.mark.asyncio
    async def test_fetch_pr_info_success(self, mock_github_service, mock_llm_service, sample_pull_request, sample_pr_review_state):
        """Test fetch_pr_info method with successful response."""
        mock_github_service.get_pull_request.return_value = sample_pull_request
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_info(sample_pr_review_state)
        
        assert result.pull_request == sample_pull_request
        assert result.error is None
        mock_github_service.get_pull_request.assert_called_once_with(
            sample_pr_review_state.pull_request.pr_number
        )

    @pytest.mark.asyncio
    async def test_fetch_pr_info_error(self, mock_github_service, mock_llm_service, sample_pr_review_state):
        """Test fetch_pr_info method when an error occurs."""
        mock_github_service.get_pull_request.side_effect = Exception("Test error")
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_info(sample_pr_review_state)
        
        assert result.pull_request == sample_pr_review_state.pull_request
        assert result.error is not None
        assert "Test error" in result.error
        assert result.completed is True
        mock_github_service.get_pull_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_pr_diff_success(self, mock_github_service, mock_llm_service, sample_file_change, sample_pr_review_state):
        """Test fetch_pr_diff method with successful response."""
        mock_github_service.get_pr_diff.return_value = [sample_file_change]
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_diff(sample_pr_review_state)
        
        assert len(result.pull_request.changes) == 1
        assert result.pull_request.changes[0] == sample_file_change
        assert result.error is None
        mock_github_service.get_pr_diff.assert_called_once_with(
            sample_pr_review_state.pull_request.pr_number
        )

    @pytest.mark.asyncio
    async def test_fetch_pr_diff_error(self, mock_github_service, mock_llm_service, sample_pr_review_state):
        """Test fetch_pr_diff method when an error occurs."""
        mock_github_service.get_pr_diff.side_effect = Exception("Test error")
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_diff(sample_pr_review_state)
        
        assert result.pull_request == sample_pr_review_state.pull_request
        assert result.error is not None
        assert "Test error" in result.error
        assert result.completed is True
        mock_github_service.get_pr_diff.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_diff_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_file_change):
        """Test analyze_diff method with successful response."""
        # Add a file change to the PR
        updated_pr = sample_pr_review_state.pull_request.copy(
            update={"changes": [sample_file_change]}
        )
        state = sample_pr_review_state.copy(update={"pull_request": updated_pr})
        
        mock_issues = [
            {
                "line_number": 10,
                "description": "Test issue",
                "severity": "medium",
                "suggestion": "Fix it"
            }
        ]
        mock_llm_service.analyze_diff.return_value = mock_issues
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.analyze_diff(state)
        
        assert sample_file_change.filename in result.analyzed_files
        assert len(result.detected_issues) == 1
        assert result.detected_issues[0]["file"] == sample_file_change.filename
        assert result.detected_issues[0]["line_number"] == 10
        assert result.error is None
        mock_llm_service.analyze_diff.assert_called_once_with(
            sample_file_change.filename, sample_file_change.patch
        )

    @pytest.mark.asyncio
    async def test_analyze_diff_skip_analyzed(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_file_change):
        """Test analyze_diff method skips already analyzed files."""
        # Add a file change to the PR
        updated_pr = sample_pr_review_state.pull_request.copy(
            update={"changes": [sample_file_change]}
        )
        # Mark the file as already analyzed
        state = sample_pr_review_state.copy(
            update={
                "pull_request": updated_pr,
                "analyzed_files": [sample_file_change.filename]
            }
        )
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.analyze_diff(state)
        
        assert sample_file_change.filename in result.analyzed_files
        assert len(result.detected_issues) == 0
        assert result.error is None
        mock_llm_service.analyze_diff.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_comments_success(self, mock_github_service, mock_llm_service, sample_pr_review_state):
        """Test generate_comments method with successful response."""
        issues = [
            {
                "file": "test_file.py",
                "line_number": 10,
                "description": "Test issue",
                "severity": "medium",
                "suggestion": "Fix it"
            }
        ]
        state = sample_pr_review_state.copy(update={"detected_issues": issues})
        
        mock_comments = [
            {
                "path": "test_file.py",
                "line": 10,
                "body": "Generated comment"
            }
        ]
        mock_llm_service.generate_pr_comments.return_value = mock_comments
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.generate_comments(state)
        
        assert len(result.comments_to_add) == 1
        assert result.comments_to_add[0].path == "test_file.py"
        assert result.comments_to_add[0].line == 10
        assert result.comments_to_add[0].body == "Generated comment"
        assert result.error is None
        mock_llm_service.generate_pr_comments.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_comments_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_comment):
        """Test add_comments method with successful response."""
        state = sample_pr_review_state.copy(update={"comments_to_add": [sample_pr_comment]})
        
        mock_github_service.add_pr_comment.return_value = sample_pr_comment
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.add_comments(state)
        
        assert len(result.comments_added) == 1
        assert result.comments_added[0] == sample_pr_comment
        assert result.completed is True
        assert result.error is None
        mock_github_service.add_pr_comment.assert_called_once_with(
            state.pull_request.pr_number, sample_pr_comment
        )

    @pytest.mark.asyncio
    async def test_add_comments_skip_duplicates(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_comment):
        """Test add_comments method skips duplicate comments."""
        state = sample_pr_review_state.copy(
            update={
                "comments_to_add": [sample_pr_comment],
                "comments_added": [sample_pr_comment]
            }
        )
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.add_comments(state)
        
        assert len(result.comments_added) == 1
        assert result.comments_added[0] == sample_pr_comment
        assert result.completed is True
        assert result.error is None
        mock_github_service.add_pr_comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_comments_error(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_comment):
        """Test add_comments method when an error occurs."""
        state = sample_pr_review_state.copy(update={"comments_to_add": [sample_pr_comment]})
        
        mock_github_service.add_pr_comment.side_effect = Exception("Test error")
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.add_comments(state)
        
        assert len(result.comments_added) == 0
        assert result.completed is True
        assert result.error is None  # Error is logged but not added to state
        mock_github_service.add_pr_comment.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_pr(self, mock_github_service, mock_llm_service):
        """Test review_pr method."""
        mock_result = MagicMock(spec=PRReviewState)
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        agent.graph = AsyncMock()
        agent.graph.ainvoke.return_value = mock_result
        
        result = await agent.review_pr(123)
        
        assert result == mock_result
        agent.graph.ainvoke.assert_called_once()
        # Check that the initial state was created correctly
        call_arg = agent.graph.ainvoke.call_args[0][0]
        assert isinstance(call_arg, PRReviewState)
        assert call_arg.pull_request.pr_number == 123
