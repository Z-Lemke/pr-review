import json
import subprocess
from typing import List, Optional, Dict, Any
import os
from datetime import datetime

from ..models.pr_models import PullRequest, FileChange, PRComment


class GitHubService:
    """Service for interacting with GitHub PRs using GitHub CLI."""

    def __init__(self, repository: Optional[str] = None):
        """
        Initialize the GitHub service.
        
        Args:
            repository: The repository in the format 'owner/repo'
        """
        self.repository = repository
        self._check_gh_cli()
    
    def _check_gh_cli(self) -> None:
        """Check if GitHub CLI is installed and authenticated."""
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError(
                "GitHub CLI (gh) is not installed or not in PATH. "
                "Please install it from https://cli.github.com/"
            )
        
        # Check if authenticated
        try:
            subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        except subprocess.SubprocessError:
            raise RuntimeError(
                "Not authenticated with GitHub CLI. "
                "Please run 'gh auth login' to authenticate."
            )

    def get_pull_request(self, pr_number: int, repository: Optional[str] = None) -> PullRequest:
        """
        Get information about a pull request.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            PullRequest object with PR information
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", 
             "number,title,body,author,createdAt,updatedAt,baseRefName,headRefName"],
            capture_output=True,
            text=True,
            check=True
        )
        
        pr_data = json.loads(result.stdout)
        
        # Parse datetime strings
        created_at = datetime.fromisoformat(pr_data["createdAt"]) if pr_data.get("createdAt") else None
        updated_at = datetime.fromisoformat(pr_data["updatedAt"]) if pr_data.get("updatedAt") else None
        
        return PullRequest(
            pr_number=pr_data["number"],
            title=pr_data["title"],
            description=pr_data["body"],
            author=pr_data["author"]["login"],
            created_at=created_at,
            updated_at=updated_at,
            base_branch=pr_data["baseRefName"],
            head_branch=pr_data["headRefName"],
            repository=repo,
            changes=[]  # Will be filled by get_pr_diff
        )
    
    def get_pr_diff(self, pr_number: int, repository: Optional[str] = None) -> List[FileChange]:
        """
        Get the diff for a pull request.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            List of FileChange objects representing changes in the PR
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        # Get the list of files changed
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "files"],
            capture_output=True,
            text=True,
            check=True
        )
        
        files_data = json.loads(result.stdout)["files"]
        
        file_changes = []
        for file_data in files_data:
            file_changes.append(
                FileChange(
                    filename=file_data["path"],
                    status=file_data.get("status", "modified"),  # Default to 'modified' if status is missing
                    patch=None,  # We'll fetch the patch separately
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0)
                )
            )
        
        # Get the full diff
        diff_result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "--repo", repo],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the diff and assign it to the correct file
        diff_lines = diff_result.stdout.splitlines()
        current_file = None
        current_patch = []
        
        for line in diff_lines:
            if line.startswith("diff --git"):
                if current_file and current_patch:
                    # Extract the filename from the diff line (format: "diff --git a/path/to/file b/path/to/file")
                    file_path = current_file.split(" b/")[-1]
                    
                    # Find the matching file change and assign the patch
                    for fc in file_changes:
                        if fc.filename == file_path:
                            fc.patch = "\n".join(current_patch)
                            break
                current_file = line
                current_patch = [line]
            else:
                current_patch.append(line)
        
        # Add the last patch if any
        if current_file and current_patch:
            file_path = current_file.split(" b/")[-1]
            for fc in file_changes:
                if fc.filename == file_path:
                    fc.patch = "\n".join(current_patch)
                    break
        
        return file_changes

    def _get_pr_head_commit(self, pr_number: int, repository: str) -> str:
        """Get the latest commit in a PR.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo'
            
        Returns:
            The commit ID of the head commit
        """
        commit_result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repository, "--json", "headRefOid"],
            capture_output=True,
            text=True,
            check=True
        )
        commit_data = json.loads(commit_result.stdout)
        return commit_data.get("headRefOid", "")
    
    def _create_temp_file(self, content: str) -> str:
        """Create a temporary file with the given content.
        
        Args:
            content: The content to write to the file
            
        Returns:
            The path to the temporary file
        """
        temp_file = f"/tmp/pr_comment_{os.getpid()}.txt"
        with open(temp_file, "w") as f:
            f.write(content)
        return temp_file
    
    def _add_line_comment_via_api(self, pr_number: int, repository: str, comment: PRComment) -> Optional[PRComment]:
        """Add a line-specific comment to a PR using the GitHub API.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo'
            comment: The comment to add
            
        Returns:
            The added comment if successful, None otherwise
        """
        try:
            # Parse owner and repo from repository string
            owner, repo_name = repository.split('/')
            
            # Prepare API endpoint
            endpoint = f"/repos/{owner}/{repo_name}/pulls/{pr_number}/comments"
            
            # Get the latest commit in the PR
            head_commit = self._get_pr_head_commit(pr_number, repository)
            
            # Prepare API request parameters
            api_params = {
                "body": comment.body,
                "path": comment.path,
                "line": comment.line,
                "commit_id": head_commit,
                "side": "RIGHT"  # Default to RIGHT side (the new code)
            }
            
            # Print equivalent curl command for debugging
            self._print_curl_command(endpoint, api_params)
            
            # Create a temporary file for the JSON payload
            json_file = f"/tmp/pr_comment_json_{os.getpid()}.json"
            try:
                with open(json_file, "w") as f:
                    json.dump(api_params, f)
                
                # Use the GitHub CLI with the --raw flag to directly access the REST API
                cmd = [
                    "gh", "api",
                    "--method", "POST",
                    "-H", "Accept: application/vnd.github+json",
                    "-H", "X-GitHub-Api-Version: 2022-11-28",
                    endpoint,
                    "--input", json_file,
                    "--jq", "."  # Output the raw JSON response
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    # Log the error details
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to add line-specific comment via API: {result.stderr}")
                    logger.debug(f"Command output: stdout={result.stdout}, stderr={result.stderr}")
                    return None
                
                # Successfully added line-specific comment
                return comment
            finally:
                # Clean up JSON file
                if os.path.exists(json_file):
                    os.remove(json_file)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to add line-specific comment via API: {str(e)}. Falling back to regular PR comment.")
            logger.debug(f"Error details: {str(e)}")
            return None
    
    def _print_curl_command(self, endpoint: str, api_params: Dict[str, Any]) -> None:
        """Print an equivalent curl command for debugging.
        
        Args:
            endpoint: The API endpoint
            api_params: The API parameters
        """
        curl_command = f"""curl -X POST \\
  -H "Accept: application/vnd.github+json" \\
  -H "Authorization: Bearer $(gh auth token)" \\
  -H "X-GitHub-Api-Version: 2022-11-28" \\
  https://api.github.com{endpoint} \\
  -d '{json.dumps(api_params)}'"""
        
        print("\nEquivalent curl command:")
        print(curl_command)
    
    def _add_regular_pr_comment(self, pr_number: int, repository: str, comment: PRComment) -> PRComment:
        """Add a regular (non-line-specific) comment to a PR.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo'
            comment: The comment to add
            
        Returns:
            The added comment
        """
        # Create a temporary file with the comment body
        temp_file = self._create_temp_file(comment.body)
        
        try:
            # Add a reference to the file and line in the comment body if this is a line comment
            if comment.path and comment.line:
                with open(temp_file, "w") as f:
                    f.write(f"**{comment.path}:{comment.line}**\n\n{comment.body}")
            
            # Add the comment to GitHub
            cmd = [
                "gh", "pr", "comment", str(pr_number),
                "--repo", repository,
                "--body-file", temp_file
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            return comment
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def add_pr_comment(self, pr_number: int, comment: PRComment, repository: Optional[str] = None, 
                       path: Optional[str] = None, line: Optional[int] = None) -> PRComment:
        """
        Add a comment to a PR.
        
        Args:
            pr_number: The PR number
            comment: The comment to add
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            path: File path where the comment should be added, overrides the path in the comment
            line: Line number where the comment should be added, overrides the line in the comment
            
        Returns:
            The added comment with any additional information from GitHub
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        # Override comment path and line if provided as separate arguments
        if path:
            comment.path = path
        if line is not None:
            comment.line = line
        
        # First try to add a line-specific comment if path and line are provided
        if comment.path and comment.line:
            line_comment = self._add_line_comment_via_api(pr_number, repo, comment)
            if line_comment:
                return line_comment
        
        # Fall back to regular PR comment
        return self._add_regular_pr_comment(pr_number, repo, comment)

    def get_pr_comments(self, pr_number: int, repository: Optional[str] = None) -> List[PRComment]:
        """
        Get comments from a PR.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            List of PRComment objects
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "comments"],
            capture_output=True,
            text=True,
            check=True
        )
        
        comments_data = json.loads(result.stdout).get("comments", [])
        
        comments = []
        for comment_data in comments_data:
            # Skip non-review comments
            if not comment_data.get("path"):
                continue
                
            comments.append(
                PRComment(
                    path=comment_data.get("path", ""),
                    line=comment_data.get("line", 0),
                    body=comment_data.get("body", ""),
                    commit_id=comment_data.get("commitId"),
                    comment_id=comment_data.get("id")
                )
            )
        
        return comments
