import pytest
from datetime import datetime
from src.models.pr_models import FileChange, PRComment, PullRequest, PRReviewState


class TestFileChange:
    def test_file_change_creation(self):
        """Test creating a FileChange object."""
        file_change = FileChange(
            filename="test.py",
            status="modified",
            patch="@@ -1,1 +1,2 @@",
            additions=1,
            deletions=0
        )
        
        assert file_change.filename == "test.py"
        assert file_change.status == "modified"
        assert file_change.patch == "@@ -1,1 +1,2 @@"
        assert file_change.additions == 1
        assert file_change.deletions == 0
    
    def test_file_change_defaults(self):
        """Test FileChange default values."""
        file_change = FileChange(
            filename="test.py",
            status="added"
        )
        
        assert file_change.filename == "test.py"
        assert file_change.status == "added"
        assert file_change.patch is None
        assert file_change.additions == 0
        assert file_change.deletions == 0


class TestPRComment:
    def test_pr_comment_creation(self):
        """Test creating a PRComment object."""
        comment = PRComment(
            path="test.py",
            line=10,
            body="This is a comment",
            commit_id="abc123",
            comment_id=456
        )
        
        assert comment.path == "test.py"
        assert comment.line == 10
        assert comment.body == "This is a comment"
        assert comment.commit_id == "abc123"
        assert comment.comment_id == 456
    
    def test_pr_comment_required_fields(self):
        """Test PRComment with only required fields."""
        comment = PRComment(
            path="test.py",
            line=10,
            body="This is a comment"
        )
        
        assert comment.path == "test.py"
        assert comment.line == 10
        assert comment.body == "This is a comment"
        assert comment.commit_id is None
        assert comment.comment_id is None


class TestPullRequest:
    def test_pull_request_creation(self, sample_file_change):
        """Test creating a PullRequest object."""
        now = datetime.now()
        pr = PullRequest(
            pr_number=123,
            title="Test PR",
            description="This is a test PR",
            author="test-user",
            created_at=now,
            updated_at=now,
            base_branch="main",
            head_branch="feature",
            repository="owner/repo",
            changes=[sample_file_change],
            comments=[PRComment(path="test.py", line=10, body="Comment")]
        )
        
        assert pr.pr_number == 123
        assert pr.title == "Test PR"
        assert pr.description == "This is a test PR"
        assert pr.author == "test-user"
        assert pr.created_at == now
        assert pr.updated_at == now
        assert pr.base_branch == "main"
        assert pr.head_branch == "feature"
        assert pr.repository == "owner/repo"
        assert len(pr.changes) == 1
        assert pr.changes[0].filename == sample_file_change.filename
        assert len(pr.comments) == 1
        assert pr.comments[0].path == "test.py"
    
    def test_pull_request_required_fields(self):
        """Test PullRequest with only required fields."""
        now = datetime.now()
        pr = PullRequest(
            pr_number=123,
            title="Test PR",
            author="test-user",
            created_at=now,
            base_branch="main",
            head_branch="feature",
            repository="owner/repo"
        )
        
        assert pr.pr_number == 123
        assert pr.title == "Test PR"
        assert pr.description is None
        assert pr.author == "test-user"
        assert pr.created_at == now
        assert pr.updated_at is None
        assert pr.base_branch == "main"
        assert pr.head_branch == "feature"
        assert pr.repository == "owner/repo"
        assert len(pr.changes) == 0
        assert len(pr.comments) == 0


class TestPRReviewState:
    def test_pr_review_state_creation(self, sample_pull_request):
        """Test creating a PRReviewState object."""
        state = PRReviewState(
            pull_request=sample_pull_request,
            analyzed_files=["test.py"],
            detected_issues=[{"line": 10, "message": "Issue"}],
            comments_to_add=[PRComment(path="test.py", line=10, body="Comment")],
            comments_added=[PRComment(path="test.py", line=10, body="Added")],
            completed=True,
            error=None
        )
        
        assert state.pull_request == sample_pull_request
        assert state.analyzed_files == ["test.py"]
        assert len(state.detected_issues) == 1
        assert state.detected_issues[0]["line"] == 10
        assert len(state.comments_to_add) == 1
        assert state.comments_to_add[0].body == "Comment"
        assert len(state.comments_added) == 1
        assert state.comments_added[0].body == "Added"
        assert state.completed is True
        assert state.error is None
    
    def test_pr_review_state_defaults(self, sample_pull_request):
        """Test PRReviewState default values."""
        state = PRReviewState(
            pull_request=sample_pull_request
        )
        
        assert state.pull_request == sample_pull_request
        assert state.analyzed_files == []
        assert state.detected_issues == []
        assert state.comments_to_add == []
        assert state.comments_added == []
        assert state.completed is False
        assert state.error is None
