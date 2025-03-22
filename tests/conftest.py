import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.pr_models import PullRequest, FileChange, PRComment, PRReviewState
from src.services.github_service import GitHubService
from src.services.llm_service import LLMService
from src.core.pr_review_agent import PRReviewAgent


@pytest.fixture
def sample_file_change():
    """Return a sample FileChange object."""
    return FileChange(
        filename="test_file.py",
        status="modified",
        patch="@@ -1,5 +1,7 @@\n def test_func():\n-    return True\n+    # Added a comment\n+    return True\n",
        additions=2,
        deletions=1
    )


@pytest.fixture
def sample_pr_comment():
    """Return a sample PRComment object."""
    return PRComment(
        path="test_file.py",
        line=42,
        body="This looks like it could be improved",
        commit_id="abc123"
    )


@pytest.fixture
def sample_pull_request(sample_file_change):
    """Return a sample PullRequest object."""
    return PullRequest(
        pr_number=123,
        title="Test PR",
        description="This is a test PR",
        author="test-user",
        created_at=datetime.now(),
        base_branch="main",
        head_branch="feature-branch",
        repository="test-owner/test-repo",
        changes=[sample_file_change]
    )


@pytest.fixture
def sample_pr_review_state(sample_pull_request):
    """Return a sample PRReviewState object."""
    return PRReviewState(
        pull_request=sample_pull_request,
        analyzed_files=[],
        detected_issues=[],
        comments_to_add=[],
        comments_added=[],
        completed=False,
        error=None
    )


@pytest.fixture
def mock_github_service():
    """Return a mocked GitHubService."""
    mock_service = MagicMock(spec=GitHubService)
    mock_service.repository = "test-owner/test-repo"
    return mock_service


@pytest.fixture
def mock_llm_service():
    """Return a mocked LLMService."""
    mock_service = MagicMock(spec=LLMService)
    return mock_service


@pytest.fixture
def mock_pr_review_agent(mock_github_service, mock_llm_service):
    """Return a mocked PRReviewAgent."""
    agent = PRReviewAgent(mock_github_service, mock_llm_service)
    # Mock the graph to avoid actual execution
    agent.graph = MagicMock()
    return agent
