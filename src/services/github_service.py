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

    def add_pr_comment(self, pr_number: int, comment: PRComment, repository: Optional[str] = None) -> PRComment:
        """
        Add a comment to a PR.
        
        Args:
            pr_number: The PR number
            comment: The comment to add
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            The added comment with any additional information from GitHub
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        # Create a temporary file with the comment body
        temp_file = f"/tmp/pr_comment_{os.getpid()}.txt"
        with open(temp_file, "w") as f:
            f.write(comment.body)
        
        try:
            # First try to add a line-specific comment if path and line are provided
            if comment.path and comment.line:
                try:
                    cmd = [
                        "gh", "pr", "comment", str(pr_number),
                        "--repo", repo,
                        "--body-file", temp_file,
                        "--file", comment.path,
                        "--line", str(comment.line)
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    
                    # Successfully added line-specific comment
                    return comment
                except subprocess.CalledProcessError as e:
                    # If line-specific comment fails, log the error and fall back to regular PR comment
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to add line-specific comment: {str(e)}. Falling back to regular PR comment.")
            
            # Add a regular PR comment (either as fallback or as the primary method)
            cmd = [
                "gh", "pr", "comment", str(pr_number),
                "--repo", repo,
                "--body-file", temp_file
            ]
            
            # Add a reference to the file and line in the comment body if this is a fallback
            if comment.path and comment.line:
                with open(temp_file, "w") as f:
                    f.write(f"**{comment.path}:{comment.line}**\n\n{comment.body}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Example result doesn't give us the comment ID, but in a real implementation
            # we would parse the response to get it
            # For now, just return the original comment
            return comment
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)

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
