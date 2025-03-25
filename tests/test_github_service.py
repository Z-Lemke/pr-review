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
        with patch.object(GitHubService, '_add_line_comment_via_api', return_value=sample_pr_comment) as mock_line_comment, \
             patch.object(GitHubService, '_add_regular_pr_comment') as mock_regular_comment, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(123, sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_line_comment.assert_called_once_with(123, "owner/repo", sample_pr_comment)
            mock_regular_comment.assert_not_called()

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
            
            mock_run.assert_called_once()

    def test_get_pr_comments_no_repository(self):
        """Test get_pr_comments method with no repository specified."""
        with patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            with pytest.raises(ValueError, match="Repository must be specified"):
                service.get_pr_comments(123)

    def test_get_pr_head_commit(self):
        """Test _get_pr_head_commit method."""
        mock_commit_data = {"headRefOid": "abc123def456"}
        
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_commit_data)
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            with patch.object(GitHubService, '_check_gh_cli'):
                service = GitHubService(repository="owner/repo")
                commit_id = service._get_pr_head_commit(123, "owner/repo")
                
                assert commit_id == "abc123def456"
                mock_run.assert_called_once_with(
                    ["gh", "pr", "view", "123", "--repo", "owner/repo", "--json", "headRefOid"],
                    capture_output=True,
                    text=True,
                    check=True
                )

    def test_create_temp_file(self):
        """Test _create_temp_file method."""
        test_content = "Test content"
        expected_path = f"/tmp/pr_comment_{os.getpid()}.txt"
        
        with patch('builtins.open', MagicMock()) as mock_open, \
             patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            result = service._create_temp_file(test_content)
            
            assert result == expected_path
            mock_open.assert_called_once_with(expected_path, "w")
            mock_open.return_value.__enter__.return_value.write.assert_called_once_with(test_content)

    def test_print_curl_command(self):
        """Test _print_curl_command method."""
        endpoint = "/repos/owner/repo/pulls/123/comments"
        api_params = {"body": "Test comment", "path": "test.py", "line": 10}
        
        with patch('builtins.print') as mock_print, \
             patch.object(GitHubService, '_check_gh_cli'):
            service = GitHubService()
            service._print_curl_command(endpoint, api_params)
            
            # Verify print was called twice (header and command)
            assert mock_print.call_count == 2
            
            # Check that the curl command contains the expected elements
            curl_command = mock_print.call_args_list[1][0][0]
            assert "curl -X POST" in curl_command
            assert "Accept: application/vnd.github+json" in curl_command
            assert "Authorization: Bearer $(gh auth token)" in curl_command
            assert endpoint in curl_command
            assert json.dumps(api_params) in curl_command

    def test_add_line_comment_via_api_success(self, sample_pr_comment):
        """Test _add_line_comment_via_api method when successful."""
        with patch('subprocess.run') as mock_run, \
             patch('builtins.open', MagicMock()), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(GitHubService, '_get_pr_head_commit', return_value="abc123"), \
             patch.object(GitHubService, '_print_curl_command'), \
             patch.object(GitHubService, '_check_gh_cli'):
            
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"id": 12345}'
            mock_run.return_value = mock_result
            
            service = GitHubService()
            result = service._add_line_comment_via_api(123, "owner/repo", sample_pr_comment)
            
            assert result == sample_pr_comment
            assert mock_run.call_count == 1
            assert "--input" in mock_run.call_args[0][0]

    def test_add_line_comment_via_api_failure(self, sample_pr_comment):
        """Test _add_line_comment_via_api method when it fails."""
        with patch('subprocess.run') as mock_run, \
             patch('builtins.open', MagicMock()), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(GitHubService, '_get_pr_head_commit', return_value="abc123"), \
             patch.object(GitHubService, '_print_curl_command'), \
             patch.object(GitHubService, '_check_gh_cli'):
            
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error: Invalid input"
            mock_run.return_value = mock_result
            
            service = GitHubService()
            result = service._add_line_comment_via_api(123, "owner/repo", sample_pr_comment)
            
            assert result is None  # Should return None on failure

    def test_add_regular_pr_comment(self, sample_pr_comment):
        """Test _add_regular_pr_comment method."""
        with patch('subprocess.run') as mock_run, \
             patch('builtins.open', MagicMock()), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch.object(GitHubService, '_create_temp_file', return_value="/tmp/test_file.txt"), \
             patch.object(GitHubService, '_check_gh_cli'):
            
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            service = GitHubService()
            result = service._add_regular_pr_comment(123, "owner/repo", sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_run.assert_called_once()
            assert "gh" in mock_run.call_args[0][0][0]
            assert "pr" in mock_run.call_args[0][0][1]
            assert "comment" in mock_run.call_args[0][0][2]

    def test_add_pr_comment_line_specific(self, sample_pr_comment):
        """Test add_pr_comment method with line-specific comment."""
        with patch.object(GitHubService, '_add_line_comment_via_api', return_value=sample_pr_comment) as mock_line_comment, \
             patch.object(GitHubService, '_add_regular_pr_comment') as mock_regular_comment, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(123, sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_line_comment.assert_called_once_with(123, "owner/repo", sample_pr_comment)
            mock_regular_comment.assert_not_called()

    def test_add_pr_comment_fallback(self, sample_pr_comment):
        """Test add_pr_comment method falling back to regular comment."""
        with patch.object(GitHubService, '_add_line_comment_via_api', return_value=None) as mock_line_comment, \
             patch.object(GitHubService, '_add_regular_pr_comment', return_value=sample_pr_comment) as mock_regular_comment, \
             patch.object(GitHubService, '_check_gh_cli'):
            
            service = GitHubService(repository="owner/repo")
            result = service.add_pr_comment(123, sample_pr_comment)
            
            assert result == sample_pr_comment
            mock_line_comment.assert_called_once_with(123, "owner/repo", sample_pr_comment)
            mock_regular_comment.assert_called_once_with(123, "owner/repo", sample_pr_comment)
