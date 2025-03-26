import json
import subprocess
from typing import List, Optional, Dict, Any
import os
import logging
from datetime import datetime

from ..models.pr_models import (
    PullRequest, 
    FileChange, 
    PRComment, 
    RepositoryInfo, 
    DocumentInfo, 
    GuidelinesInfo, 
    IssueInfo
)

logger = logging.getLogger(__name__)

class GitHubService:
    """Service for interacting with GitHub PRs using GitHub CLI."""

    def __init__(self, repository: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the GitHub service.
        
        Args:
            repository: The repository in the format 'owner/repo'
            token: GitHub token for authentication (optional, falls back to GitHub CLI auth)
        """
        self.repository = repository
        self.token = token
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
            # If token is provided, we can skip this check
            if not self.token:
                raise RuntimeError(
                    "Not authenticated with GitHub CLI. "
                    "Please run 'gh auth login' to authenticate or provide a token."
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
        
        try:
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
        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching PR info: {e.stderr}")
            raise RuntimeError(f"Failed to fetch PR info: {e.stderr}")
    
    def get_repository_info(self, repository: Optional[str] = None) -> RepositoryInfo:
        """
        Get information about a repository.
        
        Args:
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            RepositoryInfo object with repository information
        """
        repo = repository or self.repository
        if not repo:
            raise ValueError("Repository must be specified")
        
        try:
            result = subprocess.run(
                ["gh", "repo", "view", repo, "--json", 
                "name,description,defaultBranchRef,languages,repositoryTopics,hasWikiEnabled,hasIssuesEnabled,licenseInfo"],
                capture_output=True,
                text=True,
                check=True
            )
            
            repo_data = json.loads(result.stdout)
            
            # Extract languages with safe access
            languages = {}
            lang_list = repo_data.get("languages", []) or []
            for lang in lang_list:
                if isinstance(lang, dict):
                    languages[lang.get("name", "")] = lang.get("size", 0)
            
            # Extract topics with safe access
            topics = []
            topics_data = repo_data.get("repositoryTopics", {}) or {}
            nodes = topics_data.get("nodes", []) or []
            for topic in nodes:
                if isinstance(topic, dict):
                    topic_obj = topic.get("topic", {}) or {}
                    topic_name = topic_obj.get("name", "")
                    if topic_name:
                        topics.append(topic_name)
            
            # Get default branch with safe access
            default_branch_ref = repo_data.get("defaultBranchRef", {}) or {}
            default_branch = default_branch_ref.get("name", "main")
            
            # Get license info with safe access
            license_info = repo_data.get("licenseInfo", {}) or {}
            license_name = license_info.get("name", "")
            
            return RepositoryInfo(
                name=repo_data.get("name", ""),
                description=repo_data.get("description", ""),
                default_branch=default_branch,
                languages=languages,
                topics=topics,
                has_wiki=repo_data.get("hasWikiEnabled", False),
                has_issues=repo_data.get("hasIssuesEnabled", False),
                license=license_name
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI error: {e.stderr}")
            # Return a default RepositoryInfo object with minimal information
            return RepositoryInfo(
                name=repo.split("/")[-1] if "/" in repo else repo,
                description="",
                default_branch="main",
                languages={},
                topics=[],
                has_wiki=False,
                has_issues=False,
                license=""
            )
        except Exception as e:
            logger.error(f"Error getting repository info: {str(e)}")
            # Return a default RepositoryInfo object with minimal information
            return RepositoryInfo(
                name=repo.split("/")[-1] if "/" in repo else repo,
                description="",
                default_branch="main",
                languages={},
                topics=[],
                has_wiki=False,
                has_issues=False,
                license=""
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
        
        try:
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
        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching PR diff: {e.stderr}")
            raise RuntimeError(f"Failed to fetch PR diff: {e.stderr}")

    def get_complete_file(self, repository: str, file_path: str, ref: str = "HEAD") -> str:
        """
        Get the complete content of a file from a repository.
        
        Args:
            repository: The repository in the format 'owner/repo'
            file_path: The path to the file in the repository
            ref: The git reference (branch, tag, or commit)
            
        Returns:
            The content of the file as a string
        """
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{repository}/contents/{file_path}", 
                 "--method", "GET", "-f", f"ref={ref}", "-q", ".content"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # The content is base64 encoded, decode it
            import base64
            content = base64.b64decode(result.stdout.strip()).decode('utf-8')
            return content
        except subprocess.CalledProcessError as e:
            if "Not Found" in str(e.stderr):
                logger.debug(f"File not found: {file_path} in repository {repository} at ref {ref}")
            else:
                logger.warning(f"Error fetching file content for {file_path}: {e.stderr}")
            return ""

    def get_repository_structure(self, repository: str, ref: str) -> Dict[str, Any]:
        """
        Get the structure of a repository at a specific ref.
        
        Args:
            repository: The repository in the format 'owner/repo'
            ref: The git reference (branch, tag, or commit)
            
        Returns:
            Dictionary representing the repository structure
        """
        try:
            # Get the top-level directories first
            result = subprocess.run(
                ["gh", "api", f"/repos/{repository}/contents", 
                 "--method", "GET", 
                 "-f", f"ref={ref}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            contents = json.loads(result.stdout)
            structure = {}
            
            # Process top-level items
            for item in contents:
                if item["type"] == "dir":
                    structure[item["name"]] = {"type": "directory", "path": item["path"], "children": {}}
                else:
                    structure[item["name"]] = {"type": "file", "path": item["path"], "size": item["size"]}
            
            return structure
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error fetching repository structure: {e.stderr}")
            return {}

    def get_repository_docs(self, repository: str, ref: Optional[str] = None) -> List[DocumentInfo]:
        """
        Get all markdown documentation files from a repository.
        
        Args:
            repository: The repository in the format 'owner/repo'
            ref: The git reference (branch, tag, or commit)
            
        Returns:
            List of DocumentInfo objects
        """
        docs = []
        
        try:
            # First, try to use GitHub API to search for all markdown files
            logger.info(f"Searching for all markdown files in repository {repository}")
            
            # Use the GitHub API to search for files with .md extension
            result = subprocess.run(
                ["gh", "api", f"search/code?q=extension:md+repo:{repository}&per_page=100"],
                capture_output=True,
                text=True,
                check=False  # Don't raise an exception if the command fails
            )
            
            if result.returncode == 0:
                search_results = json.loads(result.stdout)
                md_files = search_results.get("items", [])
                
                # Log the number of markdown files found
                logger.info(f"Found {len(md_files)} markdown files in repository {repository}")
                
                # Process each markdown file
                for file_info in md_files:
                    file_path = file_info.get("path", "")
                    if not file_path or not file_path.endswith(".md"):
                        continue
                    
                    # Determine document type based on filename and path
                    doc_type = self._determine_doc_type(file_path)
                    
                    # Get the content of the file
                    content = self.get_complete_file(repository, file_path, ref)
                    if content:
                        docs.append(DocumentInfo(
                            path=file_path,
                            content=content,
                            type=doc_type
                        ))
                        logger.info(f"Added {doc_type} document: {file_path}")
            else:
                logger.warning(f"GitHub API search failed: {result.stderr}")
            
            # If no markdown files were found using the search API or if we got less than expected,
            # try an alternative approach using the GitHub CLI to list files
            if len(docs) < 5:  # Arbitrary threshold to determine if we need to try another approach
                logger.info("Using alternative approach to find markdown files")
                
                # Try to list all files in the repository and filter for .md files
                list_result = subprocess.run(
                    ["gh", "api", f"repos/{repository}/git/trees/HEAD?recursive=1"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if list_result.returncode == 0:
                    tree_data = json.loads(list_result.stdout)
                    tree_items = tree_data.get("tree", [])
                    
                    # Filter for markdown files
                    md_paths = [item.get("path") for item in tree_items 
                               if item.get("path", "").endswith(".md") and item.get("type") == "blob"]
                    
                    logger.info(f"Found {len(md_paths)} markdown files using tree API")
                    
                    # Process each markdown file not already in docs
                    existing_paths = {doc.path for doc in docs}
                    for file_path in md_paths:
                        if file_path in existing_paths:
                            continue
                        
                        # Determine document type based on filename and path
                        doc_type = self._determine_doc_type(file_path)
                        
                        # Get the content of the file
                        content = self.get_complete_file(repository, file_path, ref)
                        if content:
                            docs.append(DocumentInfo(
                                path=file_path,
                                content=content,
                                type=doc_type
                            ))
                            logger.info(f"Added {doc_type} document: {file_path}")
                else:
                    logger.warning(f"GitHub tree API failed: {list_result.stderr}")
            
            # If still no markdown files were found, fall back to checking common locations
            if not docs:
                logger.info("No markdown files found via APIs, checking common locations")
                doc_patterns = [
                    {"path": "README.md", "type": "README"},
                    {"path": "CONTRIBUTING.md", "type": "CONTRIBUTING"},
                    {"path": "CODE_OF_CONDUCT.md", "type": "CODE_OF_CONDUCT"},
                    {"path": "SECURITY.md", "type": "SECURITY"},
                    {"path": ".github/PULL_REQUEST_TEMPLATE.md", "type": "PR_TEMPLATE"},
                    {"path": "docs/README.md", "type": "DOCS_README"},
                    {"path": "docs/ARCHITECTURE.md", "type": "ARCHITECTURE"},
                    {"path": "docs/DESIGN.md", "type": "DESIGN"},
                    {"path": "docs/API.md", "type": "API"},
                    {"path": "docs/DEVELOPMENT.md", "type": "DEVELOPMENT"}
                ]
                
                for pattern in doc_patterns:
                    content = self.get_complete_file(repository, pattern["path"], ref)
                    if content:
                        docs.append(DocumentInfo(
                            path=pattern["path"],
                            content=content,
                            type=pattern["type"]
                        ))
                        logger.info(f"Added {pattern['type']} document: {pattern['path']}")
            
            return docs
        except Exception as e:
            logger.error(f"Error fetching repository docs: {str(e)}")
            return docs

    def get_repository_guidelines(self, repository: str) -> Optional[GuidelinesInfo]:
        """
        Get repository review guidelines from any markdown file that might contain them.
        
        Args:
            repository: The repository in the format 'owner/repo'
            
        Returns:
            GuidelinesInfo object if guidelines are found, None otherwise
        """
        # First try to find guidelines in common locations
        guideline_locations = [
            {"path": "CONTRIBUTING.md", "ref": "main"},
            {"path": ".github/PULL_REQUEST_TEMPLATE.md", "ref": "main"},
            {"path": ".github/CONTRIBUTING.md", "ref": "main"},
            {"path": "docs/CONTRIBUTING.md", "ref": "main"},
            {"path": "docs/pull_request_guidelines.md", "ref": "main"}
        ]
        
        # Check common locations first
        for location in guideline_locations:
            content = self.get_complete_file(repository, location["path"], location["ref"])
            if content:
                # Parse the content for rules
                parsed_rules = self._parse_guidelines(content)
                return GuidelinesInfo(
                    content=content,
                    source=location["path"],
                    parsed_rules=parsed_rules
                )
        
        # If not found in common locations, try to find guidelines in any markdown file
        try:
            logger.debug(f"Searching for guidelines in markdown files in repository {repository}")
            
            # Use the GitHub API to search for files with .md extension
            result = subprocess.run(
                ["gh", "api", f"search/code?q=extension:md+repo:{repository}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            search_results = json.loads(result.stdout)
            md_files = search_results.get("items", [])
            
            # Look for guidelines in each markdown file
            for file_info in md_files:
                file_path = file_info.get("path", "")
                if not file_path or not file_path.endswith(".md"):
                    continue
                
                # Skip files we've already checked
                if any(file_path == loc["path"] for loc in guideline_locations):
                    continue
                
                # Get the content of the file
                content = self.get_complete_file(repository, file_path, "main")
                if not content:
                    continue
                
                # Check if this file might contain guidelines
                lower_content = content.lower()
                if any(keyword in lower_content for keyword in ["guideline", "contributing", "pull request", "pr", "code review", "standards"]):
                    # Parse the content for rules
                    parsed_rules = self._parse_guidelines(content)
                    if parsed_rules:  # Only use if we found some rules
                        return GuidelinesInfo(
                            content=content,
                            source=file_path,
                            parsed_rules=parsed_rules
                        )
        except Exception as e:
            logger.warning(f"Error searching for guidelines in markdown files: {str(e)}")
        
        return None

    def _parse_guidelines(self, content: str) -> List[str]:
        """
        Parse guidelines content to extract rules.
        
        Args:
            content: The content of the guidelines file
            
        Returns:
            List of extracted rules
        """
        rules = []
        lines = content.split("\n")
        
        # Look for list items that might be rules
        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* ") or (line.startswith("#") and ":" in line):
                rules.append(line)
            elif line.startswith("1. ") or line.startswith("2. "):
                rules.append(line)
        
        return rules

    def get_linked_issues(self, pr_description: str) -> List[IssueInfo]:
        """
        Get issues linked in a PR description.
        
        Args:
            pr_description: The PR description
            
        Returns:
            List of IssueInfo objects
        """
        issues = []
        
        if not pr_description:
            return issues
        
        # Look for issue references like #123 or owner/repo#123
        import re
        issue_refs = re.findall(r'(?:^|\s)(?:#(\d+)|(\w+/\w+)#(\d+))', pr_description)
        
        for ref in issue_refs:
            issue_num = ref[0] or ref[2]
            repo = ref[1] or self.repository
            
            if not issue_num:
                continue
                
            try:
                issue_info = self._get_issue_info(repo, int(issue_num))
                if issue_info:
                    issues.append(issue_info)
            except Exception as e:
                logger.warning(f"Error fetching issue info: {str(e)}")
        
        return issues

    def _get_issue_info(self, repository: str, issue_number: int) -> Optional[IssueInfo]:
        """
        Get information about an issue.
        
        Args:
            repository: The repository in the format 'owner/repo'
            issue_number: The issue number
            
        Returns:
            IssueInfo object if the issue is found, None otherwise
        """
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_number), "--repo", repository, "--json", 
                 "number,title,body,labels"],
                capture_output=True,
                text=True,
                check=True
            )
            
            issue_data = json.loads(result.stdout)
            
            # Extract labels
            labels = []
            for label in issue_data.get("labels", []):
                labels.append(label.get("name", ""))
            
            return IssueInfo(
                number=issue_data["number"],
                title=issue_data["title"],
                body=issue_data["body"],
                labels=labels
            )
        except subprocess.CalledProcessError:
            return None

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
                "body": comment.content,
                "path": comment.file_path,
                "line": comment.line_number,
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
        
        logger.debug("\nEquivalent curl command:")
        logger.debug(curl_command)
    
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
        temp_file = self._create_temp_file(comment.content)
        
        try:
            # Add a reference to the file and line in the comment body if this is a line comment
            if comment.file_path and comment.line_number:
                with open(temp_file, "w") as f:
                    f.write(f"**{comment.file_path}:{comment.line_number}**\n\n{comment.content}")
            
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
        
        # First try to add a line-specific comment if path and line are provided
        if comment.file_path and comment.line_number and comment.comment_type == "inline":
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
        
        try:
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
                    comment_type = "body"
                else:
                    comment_type = "inline"
                    
                comments.append(
                    PRComment(
                        file_path=comment_data.get("path", ""),
                        line_number=comment_data.get("line", 0),
                        content=comment_data.get("body", ""),
                        commit_id=comment_data.get("commitId"),
                        comment_id=comment_data.get("id"),
                        comment_type=comment_type
                    )
                )
            
            return comments
        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching PR comments: {e.stderr}")
            return []

    def check_comment_thread_exists(self, pr_number: int, file_path: str, line: int) -> bool:
        """
        Check if a comment thread already exists for a specific file and line.
        
        Args:
            pr_number: The PR number
            file_path: The file path
            line: The line number
            
        Returns:
            True if a comment thread exists, False otherwise
        """
        comments = self.get_pr_comments(pr_number)
        
        for comment in comments:
            if comment.file_path == file_path and comment.line_number == line:
                return True
                
        return False

    def approve_pr(self, pr_number: int, message: str = "LGTM") -> bool:
        """
        Approve a PR.
        
        Args:
            pr_number: The PR number
            message: The approval message
            
        Returns:
            True if the PR was approved, False otherwise
        """
        repo = self.repository
        if not repo:
            raise ValueError("Repository must be specified")
            
        try:
            # Create a temporary file with the approval message
            temp_file = self._create_temp_file(message)
            
            try:
                # Approve the PR
                cmd = [
                    "gh", "pr", "review", str(pr_number),
                    "--repo", repo,
                    "--approve",
                    "--body-file", temp_file
                ]
                
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                return True
            finally:
                # Clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error approving PR: {e.stderr}")
            return False

    def _determine_doc_type(self, file_path: str) -> str:
        """
        Determine the type of a documentation file based on its path.
        
        Args:
            file_path: Path to the documentation file
            
        Returns:
            String representing the document type
        """
        file_name = file_path.split("/")[-1].lower()
        
        if "readme" in file_name:
            return "README"
        elif "contributing" in file_name:
            return "CONTRIBUTING"
        elif "code_of_conduct" in file_name or "codeofconduct" in file_name:
            return "CODE_OF_CONDUCT"
        elif "security" in file_name:
            return "SECURITY"
        elif "pull_request_template" in file_name or "pr_template" in file_name:
            return "PR_TEMPLATE"
        elif "architecture" in file_name:
            return "ARCHITECTURE"
        elif "design" in file_name:
            return "DESIGN"
        elif "api" in file_name:
            return "API"
        elif file_path.startswith("docs/"):
            return "DOCUMENTATION"
        else:
            return "OTHER"
