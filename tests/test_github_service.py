import pytest
from unittest.mock import patch, MagicMock, call
import subprocess
import json
from datetime import datetime
import os
from src.services.github_service import GitHubService
from src.models.pr_models import (
    PullRequest,
    FileChange,
    PRComment,
    RepositoryInfo,
    DocumentInfo,
    GuidelinesInfo,
    IssueInfo
)


@pytest.fixture
def sample_pr_comment():
    """Sample PRComment for testing."""
    return PRComment(
        file_path="test_file.py",
        line_number=10,
        content="This is a test comment",
        comment_type="inline"
    )


class TestGitHubService:
    def test_init(self):
        """Test GitHubService initialization."""
        with patch.object(GitHubService, '_check_gh_cli') as mock_check:
            service = GitHubService(repository="owner/repo")
            assert service.repository == "owner/repo"
            mock_check.assert_called_once()

    def test_init_with_token(self):
        """Test GitHubService initialization with token."""
        with patch.object(GitHubService, '_check_gh_cli') as mock_check:
            service = GitHubService(repository="owner/repo", token="test-token")
            assert service.repository == "owner/repo"
            assert service.token == "test-token"
            mock_check.assert_called_once()

    def test_check_gh_cli_success(self):
        """Test _check_gh_cli when GitHub CLI is installed and authenticated."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            service = GitHubService()
            # No exception should be raised

    def test_check_gh_cli_not_installed(self):
        """Test _check_gh_cli when GitHub CLI is not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(RuntimeError, match="GitHub CLI .* is not installed"):
                GitHubService()

    def test_check_gh_cli_not_authenticated(self):
        """Test _check_gh_cli when GitHub CLI is not authenticated."""
        with patch('subprocess.run') as mock_run:
            # First call succeeds (version check), second fails (auth check)
            mock_run.side_effect = [
                MagicMock(returncode=0),
                subprocess.SubprocessError()
            ]
            with pytest.raises(RuntimeError, match="Not authenticated with GitHub CLI"):
                GitHubService()

    def test_get_pull_request(self):
        """Test get_pull_request method."""
        mock_pr_data = {
            "number": 123,
            "title": "Test PR",
            "body": "Description",
            "author": {"login": "test-user"},
            "createdAt": "2023-01-01T00:00:00Z",
            "updatedAt": "2023-01-02T00:00:00Z",
            "baseRefName": "main",
            "headRefName": "feature"
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_pr_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                pr = service.get_pull_request(pr_number=123)
                
                assert pr.pr_number == 123
                assert pr.title == "Test PR"
                assert pr.description == "Description"
                assert pr.author == "test-user"
                assert pr.base_branch == "main"
                assert pr.head_branch == "feature"
                assert pr.repository == "owner/repo"
                
                mock_run.assert_called_once_with(
                    ["gh", "pr", "view", "123", "--repo", "owner/repo", "--json", 
                     "number,title,body,author,createdAt,updatedAt,baseRefName,headRefName"],
                    capture_output=True,
                    text=True,
                    check=True
                )

    def test_get_pull_request_no_repository(self):
        """Test get_pull_request method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_pull_request(pr_number=123)

    def test_get_pr_diff(self):
        """Test get_pr_diff method."""
        mock_files_data = {
            "files": [
                {
                    "path": "test_file.py",
                    "status": "modified",
                    "additions": 5,
                    "deletions": 2
                }
            ]
        }
        
        mock_diff = "diff --git a/test_file.py b/test_file.py\n@@ -1,5 +1,8 @@\n..."
        
        with patch('subprocess.run') as mock_run:
            # First call returns file list, second call returns diff
            mock_files_result = MagicMock()
            mock_files_result.stdout = json.dumps(mock_files_data)
            mock_files_result.returncode = 0
            
            mock_diff_result = MagicMock()
            mock_diff_result.stdout = mock_diff
            mock_diff_result.returncode = 0
            
            mock_run.side_effect = [mock_files_result, mock_diff_result]
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                changes = service.get_pr_diff(pr_number=123)
                
                assert len(changes) == 1
                assert changes[0].filename == "test_file.py"
                assert changes[0].status == "modified"
                assert changes[0].additions == 5
                assert changes[0].deletions == 2
                assert "diff --git" in changes[0].patch
                
                assert mock_run.call_count == 2
                mock_run.assert_has_calls([
                    call(
                        ["gh", "pr", "view", "123", "--repo", "owner/repo", "--json", "files"],
                        capture_output=True,
                        text=True,
                        check=True
                    ),
                    call(
                        ["gh", "pr", "diff", "123", "--repo", "owner/repo"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                ])

    def test_get_pr_diff_no_repository(self):
        """Test get_pr_diff method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_pr_diff(pr_number=123)

    def test_get_repository_info(self):
        """Test get_repository_info method."""
        mock_repo_data = {
            "name": "test-repo",
            "description": "A test repository",
            "defaultBranchRef": {"name": "main"},
            "languages": {"edges": [{"node": {"name": "Python"}, "size": 10000}]},
            "repositoryTopics": {"nodes": [{"topic": {"name": "testing"}}]},
            "hasWikiEnabled": True,
            "hasIssuesEnabled": True,
            "licenseInfo": {"name": "MIT"}
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_repo_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                repo_info = service.get_repository_info()
                
                assert repo_info.name == "test-repo"
                assert repo_info.description == "A test repository"
                assert repo_info.default_branch == "main"
                assert repo_info.languages == {"Python": 10000}
                assert repo_info.topics == ["testing"]
                assert repo_info.has_wiki is True
                assert repo_info.has_issues is True
                assert repo_info.license == "MIT"
                
                mock_run.assert_called_once()
                # Check that the command contains the repository name
                assert "owner/repo" in mock_run.call_args[0][0]

    def test_get_repository_info_no_repository(self):
        """Test get_repository_info method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_repository_info()

    def test_get_repository_structure(self):
        """Test get_repository_structure method."""
        mock_files_data = [
            "README.md",
            "src/main.py",
            "tests/test_main.py"
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "\n".join(mock_files_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                structure = service.get_repository_structure(ref="main")
                
                assert len(structure) == 3
                assert "README.md" in structure
                assert "src/main.py" in structure
                assert "tests/test_main.py" in structure
                
                mock_run.assert_called_once()
                # Check that the command contains the repository and ref
                cmd = mock_run.call_args[0][0]
                assert "owner/repo" in cmd
                assert "main" in cmd

    def test_get_repository_structure_no_repository(self):
        """Test get_repository_structure method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_repository_structure(ref="main")

    def test_get_repository_docs(self):
        """Test get_repository_docs method."""
        mock_files_data = [
            "README.md",
            "CONTRIBUTING.md",
            "docs/guide.md"
        ]
        
        mock_file_contents = {
            "README.md": "# Test Repo\nThis is a test repository.",
            "CONTRIBUTING.md": "# Contributing\nFollow these guidelines.",
            "docs/guide.md": "# User Guide\nHow to use the project."
        }
        
        with patch('subprocess.run') as mock_run, \
             patch.object(GitHubService, 'get_repository_structure') as mock_structure, \
             patch.object(GitHubService, 'get_file_content') as mock_file_content:
            
            mock_structure.return_value = mock_files_data
            mock_file_content.side_effect = lambda path, ref: mock_file_contents.get(path, "")
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                docs = service.get_repository_docs(ref="main")
                
                assert len(docs) == 3
                
                # Check README
                readme = next(d for d in docs if d.path == "README.md")
                assert readme.content == "# Test Repo\nThis is a test repository."
                assert readme.type == "README"
                
                # Check CONTRIBUTING
                contributing = next(d for d in docs if d.path == "CONTRIBUTING.md")
                assert contributing.content == "# Contributing\nFollow these guidelines."
                assert contributing.type == "CONTRIBUTING"
                
                # Check other doc
                guide = next(d for d in docs if d.path == "docs/guide.md")
                assert guide.content == "# User Guide\nHow to use the project."
                assert guide.type == "DOCUMENTATION"
                
                mock_structure.assert_called_once_with(ref="main")
                assert mock_file_content.call_count == 3

    def test_get_repository_docs_no_repository(self):
        """Test get_repository_docs method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_repository_docs(ref="main")

    def test_get_repository_guidelines(self):
        """Test get_repository_guidelines method."""
        mock_files_data = [
            "README.md",
            "CONTRIBUTING.md",
            "STYLE_GUIDE.md"
        ]
        
        mock_file_contents = {
            "CONTRIBUTING.md": "# Contributing\n- Write tests\n- Follow PEP8",
            "STYLE_GUIDE.md": "# Style Guide\n- Use 4 spaces\n- Max line length 100"
        }
        
        with patch('subprocess.run') as mock_run, \
             patch.object(GitHubService, 'get_repository_structure') as mock_structure, \
             patch.object(GitHubService, 'get_file_content') as mock_file_content, \
             patch.object(GitHubService, '_parse_guidelines') as mock_parse:
            
            mock_structure.return_value = mock_files_data
            mock_file_content.side_effect = lambda path, ref: mock_file_contents.get(path, "")
            mock_parse.side_effect = lambda content: [line.strip("- ") for line in content.split("\n") if line.startswith("- ")]
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                guidelines = service.get_repository_guidelines()
                
                assert guidelines.source == "CONTRIBUTING.md"
                assert guidelines.content == "# Contributing\n- Write tests\n- Follow PEP8"
                assert guidelines.parsed_rules == ["Write tests", "Follow PEP8"]
                
                mock_structure.assert_called_once()
                assert mock_file_content.call_count >= 1
                mock_parse.assert_called_once_with("# Contributing\n- Write tests\n- Follow PEP8")

    def test_get_repository_guidelines_no_repository(self):
        """Test get_repository_guidelines method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_repository_guidelines()

    def test_get_repository_guidelines_not_found(self):
        """Test get_repository_guidelines method when no guidelines are found."""
        mock_files_data = [
            "README.md",
            "src/main.py"
        ]
        
        with patch.object(GitHubService, 'get_repository_structure') as mock_structure:
            mock_structure.return_value = mock_files_data
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                guidelines = service.get_repository_guidelines()
                
                assert guidelines.source == "default"
                assert "No explicit guidelines" in guidelines.content
                assert len(guidelines.parsed_rules) > 0  # Should have default rules

    def test_get_file_content(self):
        """Test get_file_content method."""
        mock_content = "def test_func():\n    return 'test'"
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_content
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                content = service.get_file_content("src/main.py", ref="main")
                
                assert content == mock_content
                
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                assert "owner/repo" in cmd
                assert "src/main.py" in cmd
                assert "main" in cmd

    def test_get_file_content_no_repository(self):
        """Test get_file_content method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_file_content("src/main.py", ref="main")

    def test_get_complete_file(self):
        """Test get_complete_file method."""
        mock_content = "def test_func():\n    return 'test'"
        
        with patch.object(GitHubService, 'get_file_content') as mock_get_content:
            mock_get_content.return_value = mock_content
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                content = service.get_complete_file(file_path="src/main.py", ref="main")
                
                assert content == mock_content
                mock_get_content.assert_called_once_with("src/main.py", ref="main")

    def test_get_linked_issues(self):
        """Test get_linked_issues method."""
        mock_pr_data = {
            "closingIssuesReferences": {
                "nodes": [
                    {
                        "number": 42,
                        "title": "Test Issue",
                        "body": "This is a test issue",
                        "labels": {"nodes": [{"name": "bug"}, {"name": "enhancement"}]}
                    }
                ]
            }
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_pr_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                issues = service.get_linked_issues(pr_number=123)
                
                assert len(issues) == 1
                assert issues[0].number == 42
                assert issues[0].title == "Test Issue"
                assert issues[0].body == "This is a test issue"
                assert issues[0].labels == ["bug", "enhancement"]
                
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                assert "123" in cmd
                assert "owner/repo" in cmd

    def test_get_linked_issues_no_repository(self):
        """Test get_linked_issues method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_linked_issues(pr_number=123)

    def test_check_comment_thread_exists(self):
        """Test check_comment_thread_exists method."""
        mock_comments_data = {
            "comments": [
                {
                    "path": "test_file.py",
                    "line": 10,
                    "body": "Existing comment"
                }
            ]
        }
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_comments_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                
                # Test with existing comment thread
                exists = service.check_comment_thread_exists(
                    pr_number=123,
                    file_path="test_file.py",
                    line=10
                )
                assert exists is True
                
                # Test with non-existing comment thread
                exists = service.check_comment_thread_exists(
                    pr_number=123,
                    file_path="test_file.py",
                    line=20
                )
                assert exists is False
                
                mock_run.assert_called_once()

    def test_add_pr_comment(self, sample_pr_comment):
        """Test add_pr_comment method."""
        with patch.object(GitHubService, '_add_line_comment_via_api', return_value=sample_pr_comment) as mock_line_comment, \
             patch.object(GitHubService, '_add_regular_pr_comment') as mock_regular_comment, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(pr_number=123, comment=sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_line_comment.assert_called_once_with(123, "owner/repo", sample_pr_comment)
            mock_regular_comment.assert_not_called()

    def test_add_pr_comment_body(self, sample_pr_comment):
        """Test add_pr_comment method with a body comment."""
        body_comment = PRComment(
            content="This is a body comment",
            comment_type="body"
        )
        
        with patch.object(GitHubService, '_add_line_comment_via_api') as mock_line_comment, \
             patch.object(GitHubService, '_add_regular_pr_comment', return_value=body_comment) as mock_regular_comment, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(pr_number=123, comment=body_comment)
            
            assert result == body_comment
            mock_line_comment.assert_not_called()
            mock_regular_comment.assert_called_once_with(123, "owner/repo", body_comment)

    def test_add_pr_comment_no_repository(self, sample_pr_comment):
        """Test add_pr_comment method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.add_pr_comment(pr_number=123, comment=sample_pr_comment)

    def test_get_pr_comments(self):
        """Test get_pr_comments method."""
        mock_comments_data = {
            "comments": [
                {
                    "path": "test_file.py",
                    "line": 10,
                    "body": "Comment text",
                    "id": 456
                },
                {
                    # Non-review comment (no path)
                    "body": "General comment"
                }
            ]
        }
        
        with patch('subprocess.run') as mock_run, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_comments_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            service = GitHubService(repository="owner/repo")
            comments = service.get_pr_comments(pr_number=123)
            
            assert len(comments) == 1  # Only review comments
            assert comments[0].file_path == "test_file.py"
            assert comments[0].line_number == 10
            assert comments[0].content == "Comment text"
            
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "123" in cmd
            assert "owner/repo" in cmd
