import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio
from datetime import datetime

from src.core.pr_review_agent import PRReviewAgent
from src.models.pr_models import (
    PRReviewState, 
    PullRequest, 
    FileChange, 
    PRComment, 
    PRIssue,
    RepositoryInfo,
    DocumentInfo,
    GuidelinesInfo,
    IssueInfo
)


@pytest.fixture
def mock_github_service():
    """Mock GitHub service for testing."""
    return MagicMock()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    return MagicMock()


@pytest.fixture
def sample_pull_request():
    """Sample PullRequest for testing."""
    return PullRequest(
        pr_number=123,
        title="Test PR",
        description="This is a test PR",
        author="test-user",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        base_branch="main",
        head_branch="feature-branch",
        repository="test-owner/test-repo",
        changes=[]
    )


@pytest.fixture
def sample_file_change():
    """Sample FileChange for testing."""
    return FileChange(
        filename="test_file.py",
        status="modified",
        patch="@@ -1,5 +1,5 @@\n def test_func():\n-    return 'old'\n+    return 'new'",
        additions=1,
        deletions=1
    )


@pytest.fixture
def sample_repository_info():
    """Sample RepositoryInfo for testing."""
    return RepositoryInfo(
        name="test-repo",
        description="A test repository",
        default_branch="main",
        languages={"Python": 10000},
        topics=["testing"],
        has_wiki=True,
        has_issues=True,
        license="MIT"
    )


@pytest.fixture
def sample_guidelines_info():
    """Sample GuidelinesInfo for testing."""
    return GuidelinesInfo(
        content="# Guidelines\n- Write tests\n- Follow PEP8",
        source="CONTRIBUTING.md",
        parsed_rules=["Write tests", "Follow PEP8"]
    )


@pytest.fixture
def sample_document_info():
    """Sample DocumentInfo for testing."""
    return DocumentInfo(
        path="README.md",
        content="# Test Repo\nThis is a test repository.",
        type="README"
    )


@pytest.fixture
def sample_issue_info():
    """Sample IssueInfo for testing."""
    return IssueInfo(
        number=42,
        title="Test Issue",
        body="This is a test issue",
        labels=["bug", "enhancement"]
    )


@pytest.fixture
def sample_pr_issue():
    """Sample PRIssue for testing."""
    return PRIssue(
        file_path="test_file.py",
        line_number=42,
        description="This looks like it could be improved",
        suggestion="Consider using a more descriptive variable name",
        severity="medium",
        guideline_violation=None
    )


@pytest.fixture
def sample_pr_comment():
    """Sample PRComment for testing."""
    return PRComment(
        file_path="test_file.py",
        line_number=42,
        content="**MEDIUM**: This looks like it could be improved\n\n**Suggestion**: Consider using a more descriptive variable name",
        comment_type="inline"
    )


@pytest.fixture
def sample_pr_review_state(sample_pull_request):
    """Sample PRReviewState for testing."""
    return PRReviewState(
        pr_number=123,
        repository="test-owner/test-repo",
        pull_request=sample_pull_request,
        repository_info=None,
        review_guidelines=None,
        pr_description_analysis=None,
        linked_issues=None,
        issues=[]
    )


class TestPRReviewAgent:
    def test_init(self, mock_github_service, mock_llm_service):
        """Test PRReviewAgent initialization."""
        with patch.object(PRReviewAgent, '_create_workflow') as mock_create:
            mock_create.return_value = MagicMock()
            
            agent = PRReviewAgent(
                github_service=mock_github_service, 
                llm_service=mock_llm_service
            )
            
            assert agent.github_service == mock_github_service
            assert agent.llm_service == mock_llm_service
            mock_create.assert_called_once()

    def test_init_with_repo_and_token(self):
        """Test PRReviewAgent initialization with repository and token."""
        with patch('src.core.pr_review_agent.GitHubService') as mock_gh_service, \
             patch('src.core.pr_review_agent.LLMService') as mock_llm_service, \
             patch.object(PRReviewAgent, '_create_workflow') as mock_create:
            
            mock_create.return_value = MagicMock()
            mock_gh_service_instance = MagicMock()
            mock_llm_service_instance = MagicMock()
            mock_gh_service.return_value = mock_gh_service_instance
            mock_llm_service.return_value = mock_llm_service_instance
            
            agent = PRReviewAgent(
                repository="test-owner/test-repo",
                github_token="test-token"
            )
            
            mock_gh_service.assert_called_once_with(
                repository="test-owner/test-repo",
                token="test-token"
            )
            mock_llm_service.assert_called_once()
            assert agent.github_service == mock_gh_service_instance
            assert agent.llm_service == mock_llm_service_instance

    def test_create_workflow(self, mock_github_service, mock_llm_service):
        """Test _create_workflow method."""
        with patch('src.core.pr_review_agent.StateGraph') as mock_state_graph:
            mock_graph = MagicMock()
            mock_state_graph.return_value = mock_graph
            mock_graph.compile.return_value = "compiled_workflow"
            
            agent = PRReviewAgent(mock_github_service, mock_llm_service)
            # Call the method directly instead of relying on the mock
            result = agent._create_workflow()
            
            # Verify the StateGraph was created with PRReviewState
            mock_state_graph.assert_called_once_with(PRReviewState)
            
            # Verify nodes were added
            assert mock_graph.add_node.call_count >= 5  # At least the basic nodes
            
            # Verify edges were added
            assert mock_graph.add_edge.call_count >= 4  # At least the basic edges
            
            # Verify the workflow was compiled
            mock_graph.compile.assert_called_once()
            assert result == "compiled_workflow"

    @pytest.mark.asyncio
    async def test_review_pr(self, mock_github_service, mock_llm_service):
        """Test review_pr method."""
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke.return_value = "final_state"
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        agent.workflow = mock_workflow
        
        result = await agent.review_pr(123, "test-owner/test-repo")
        
        # Verify the workflow was invoked with the correct initial state
        mock_workflow.ainvoke.assert_called_once()
        call_args = mock_workflow.ainvoke.call_args[0][0]
        assert call_args.pr_number == 123
        assert call_args.repository == "test-owner/test-repo"
        
        assert result == "final_state"

    @pytest.mark.asyncio
    async def test_fetch_pr_info_success(self, mock_github_service, mock_llm_service, sample_pull_request, sample_pr_review_state):
        """Test fetch_pr_info method with successful response."""
        mock_github_service.get_pull_request.return_value = sample_pull_request
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_info(sample_pr_review_state)
        
        assert result.pull_request == sample_pull_request
        mock_github_service.get_pull_request.assert_called_once_with(
            pr_number=sample_pr_review_state.pr_number,
            repository=sample_pr_review_state.repository
        )

    @pytest.mark.asyncio
    async def test_fetch_pr_info_error(self, mock_github_service, mock_llm_service, sample_pr_review_state):
        """Test fetch_pr_info method when an error occurs."""
        mock_github_service.get_pull_request.side_effect = Exception("Test error")
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        
        with pytest.raises(Exception, match="Test error"):
            await agent.fetch_pr_info(sample_pr_review_state)
        
        mock_github_service.get_pull_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_repository_info_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_repository_info):
        """Test fetch_repository_info method with successful response."""
        mock_github_service.get_repository_info.return_value = sample_repository_info
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_repository_info(sample_pr_review_state)
        
        assert result.repository_info == sample_repository_info
        mock_github_service.get_repository_info.assert_called_once_with(
            repository=sample_pr_review_state.pull_request.repository
        )

    @pytest.mark.asyncio
    async def test_fetch_repository_info_error(self, mock_github_service, mock_llm_service, sample_pr_review_state):
        """Test fetch_repository_info method when an error occurs."""
        mock_github_service.get_repository_info.side_effect = Exception("Test error")
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_repository_info(sample_pr_review_state)
        
        # Should continue workflow even if repository info fetch fails
        assert result == sample_pr_review_state
        mock_github_service.get_repository_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_repository_guidelines_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_guidelines_info):
        """Test fetch_repository_guidelines method with successful response."""
        mock_github_service.get_repository_guidelines.return_value = sample_guidelines_info
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_repository_guidelines(sample_pr_review_state)
        
        assert result.review_guidelines == sample_guidelines_info
        mock_github_service.get_repository_guidelines.assert_called_once_with(
            repository=sample_pr_review_state.pull_request.repository
        )

    @pytest.mark.asyncio
    async def test_fetch_pr_diff_success(self, mock_github_service, mock_llm_service, sample_file_change, sample_pr_review_state):
        """Test fetch_pr_diff method with successful response."""
        mock_github_service.get_pr_diff.return_value = [sample_file_change]
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_pr_diff(sample_pr_review_state)
        
        assert len(result.pull_request.changes) == 1
        assert result.pull_request.changes[0] == sample_file_change
        mock_github_service.get_pr_diff.assert_called_once_with(
            pr_number=sample_pr_review_state.pr_number,
            repository=sample_pr_review_state.pull_request.repository
        )

    @pytest.mark.asyncio
    async def test_fetch_complete_files_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_file_change):
        """Test fetch_complete_files method with successful response."""
        # Set up the state with a file change
        updated_pr = sample_pr_review_state.pull_request.model_copy(update={"changes": [sample_file_change]})
        state = sample_pr_review_state.model_copy(update={"pull_request": updated_pr})
        
        mock_github_service.get_complete_file.return_value = "def test_func():\n    return 'new'"
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.fetch_complete_files(state)
        
        assert len(result.pull_request.changes) == 1
        assert hasattr(result.pull_request.changes[0], 'full_content')
        assert result.pull_request.changes[0].full_content == "def test_func():\n    return 'new'"
        mock_github_service.get_complete_file.assert_called_once_with(
            repository=sample_pr_review_state.pull_request.repository,
            file_path=sample_file_change.filename,
            ref=sample_pr_review_state.pull_request.head_branch
        )

    @pytest.mark.asyncio
    async def test_analyze_diff_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_file_change):
        """Test analyze_diff method with successful response."""
        # Set up the file change with full content
        file_change_with_content = sample_file_change.model_copy(update={"full_content": "def test_func():\n    return 'new'"})
        
        # Set up the state with a file change
        updated_pr = sample_pr_review_state.pull_request.model_copy(update={"changes": [file_change_with_content]})
        state = sample_pr_review_state.model_copy(update={"pull_request": updated_pr})
        
        # Mock the analyze_diff_with_context response
        mock_llm_service.analyze_diff_with_context.return_value = [
            {
                "line": 2,
                "description": "This looks like it could be improved",
                "suggestion": "Consider using a more descriptive variable name",
                "severity": "medium"
            }
        ]
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.analyze_diff(state)
        
        assert len(result.issues) == 1
        assert result.issues[0].file_path == "test_file.py"
        assert result.issues[0].line_number == 2
        assert result.issues[0].description == "This looks like it could be improved"
        assert result.issues[0].suggestion == "Consider using a more descriptive variable name"
        assert result.issues[0].severity == "medium"
        
        mock_llm_service.analyze_diff_with_context.assert_called_once_with(
            file_path=file_change_with_content.filename,
            diff_content=file_change_with_content.patch,
            full_file_content=file_change_with_content.full_content,
            guidelines=state.review_guidelines,
            repository_docs=state.repository_docs
        )

    @pytest.mark.asyncio
    async def test_analyze_diff_fallback(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_file_change):
        """Test analyze_diff method falls back to basic analysis when full content is not available."""
        # Set up the state with a file change (without full content)
        updated_pr = sample_pr_review_state.pull_request.model_copy(update={"changes": [sample_file_change]})
        state = sample_pr_review_state.model_copy(update={"pull_request": updated_pr})
        
        # Mock the analyze_diff response
        mock_llm_service.analyze_diff.return_value = [
            {
                "line": 2,
                "description": "This looks like it could be improved",
                "suggestion": "Consider using a more descriptive variable name",
                "severity": "medium"
            }
        ]
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.analyze_diff(state)
        
        assert len(result.issues) == 1
        mock_llm_service.analyze_diff.assert_called_once()
        mock_llm_service.analyze_diff_with_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_comments_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_issue):
        """Test generate_comments method with successful response."""
        # Set up the state with issues
        state = sample_pr_review_state.model_copy(update={"issues": [sample_pr_issue]})
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.generate_comments(state)
        
        assert len(result.comments) == 2  # One inline comment + one summary comment
        
        # Check inline comment
        inline_comment = next(c for c in result.comments if c.comment_type == "inline")
        assert inline_comment.file_path == "test_file.py"
        assert inline_comment.line_number == 42
        assert "This looks like it could be improved" in inline_comment.content
        assert "Consider using a more descriptive variable name" in inline_comment.content
        
        # Check summary comment
        summary_comment = next(c for c in result.comments if c.comment_type == "body")
        assert "PR Review Summary" in summary_comment.content
        assert "MEDIUM Severity Issues" in summary_comment.content
        assert "test_file.py:42" in summary_comment.content

    @pytest.mark.asyncio
    async def test_add_comments_success(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_comment):
        """Test add_comments method with successful response."""
        # Set up the state with comments
        state = sample_pr_review_state.model_copy(update={"comments": [sample_pr_comment]})
        
        mock_github_service.check_comment_thread_exists.return_value = False
        mock_github_service.add_pr_comment.return_value = sample_pr_comment
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.add_comments(state)
        
        assert len(result.added_comments) == 1
        assert result.added_comments[0] == sample_pr_comment
        
        mock_github_service.check_comment_thread_exists.assert_called_once_with(
            pr_number=sample_pr_review_state.pr_number,
            file_path=sample_pr_comment.file_path,
            line=sample_pr_comment.line_number
        )
        
        mock_github_service.add_pr_comment.assert_called_once_with(
            pr_number=sample_pr_review_state.pr_number,
            comment=sample_pr_comment,
            repository=sample_pr_review_state.pull_request.repository
        )

    @pytest.mark.asyncio
    async def test_add_comments_skip_existing(self, mock_github_service, mock_llm_service, sample_pr_review_state, sample_pr_comment):
        """Test add_comments method skips existing comment threads."""
        # Set up the state with comments
        state = sample_pr_review_state.model_copy(update={"comments": [sample_pr_comment]})
        
        mock_github_service.check_comment_thread_exists.return_value = True
        
        agent = PRReviewAgent(mock_github_service, mock_llm_service)
        result = await agent.add_comments(state)
        
        assert len(result.added_comments) == 0
        mock_github_service.add_pr_comment.assert_not_called()
