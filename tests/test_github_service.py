import pytest
from unittest.mock import patch, MagicMock, call
import subprocess
import json
from datetime import datetime
import os
from src.services.github_service import GitHubService
from src.models.pr_models import PullRequest, FileChange, PRComment


class TestGitHubService:
    def test_init(self):
        """Test GitHubService initialization."""
        with patch.object(GitHubService, '_check_gh_cli') as mock_check:
            service = GitHubService(repository="owner/repo")
            assert service.repository == "owner/repo"
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
                pr = service.get_pull_request(123)
                
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
                service.get_pull_request(123)

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
                changes = service.get_pr_diff(123)
                
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
                service.get_pr_diff(123)

    def test_add_pr_comment(self, sample_pr_comment):
        """Test add_pr_comment method."""
        with patch('subprocess.run') as mock_run, \
             patch('builtins.open', MagicMock()), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(GitHubService, '_check_gh_cli'):
            
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(123, sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_run.assert_called_once()

    def test_add_pr_comment_no_repository(self, sample_pr_comment):
        """Test add_pr_comment method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.add_pr_comment(123, sample_pr_comment)

    def test_get_pr_comments(self):
        """Test get_pr_comments method."""
        mock_comments_data = {
            "comments": [
                {
                    "path": "test_file.py",
                    "line": 10,
                    "body": "Comment text",
                    "commitId": "abc123",
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
            comments = service.get_pr_comments(123)
            
            assert len(comments) == 1  # Only review comments
            assert comments[0].path == "test_file.py"
            assert comments[0].line == 10
            assert comments[0].body == "Comment text"
            assert comments[0].commit_id == "abc123"
            assert comments[0].comment_id == 456
            
            mock_run.assert_called_once_with(
                ["gh", "pr", "view", "123", "--repo", "owner/repo", "--json", "comments"],
                capture_output=True,
                text=True,
                check=True
            )

    def test_get_pr_comments_no_repository(self):
        """Test get_pr_comments method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_pr_comments(123)
