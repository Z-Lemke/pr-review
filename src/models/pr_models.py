from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class FileChange(BaseModel):
    """Represents a file change in a PR."""
    filename: str
    status: str = Field(description="Status of the file: added, modified, deleted, etc.")
    patch: Optional[str] = Field(None, description="The actual diff content")
    additions: int = 0
    deletions: int = 0


class RepositoryInfo(BaseModel):
    """Represents information about a repository."""
    name: str
    description: Optional[str] = None
    default_branch: str
    languages: Dict[str, int] = Field(default_factory=dict)
    topics: List[str] = Field(default_factory=list)
    has_wiki: bool = False
    has_issues: bool = False
    license: Optional[str] = None


class DocumentInfo(BaseModel):
    """Represents a documentation file in a repository."""
    path: str
    content: str
    type: str = Field(description="Type of document, e.g., 'README', 'CONTRIBUTING', 'CODE_OF_CONDUCT'")


class GuidelinesInfo(BaseModel):
    """Represents repository review guidelines."""
    content: str
    source: str = Field(description="Source of the guidelines, e.g., 'CONTRIBUTING.md', '.github/PULL_REQUEST_TEMPLATE.md'")
    parsed_rules: List[str] = Field(default_factory=list)


class IssueInfo(BaseModel):
    """Represents an issue linked to a PR."""
    number: int
    title: str
    body: str
    labels: List[str] = Field(default_factory=list)


class PRIssue(BaseModel):
    """Represents an issue found in a PR."""
    file_path: str = Field(description="File path where the issue was found")
    line_number: Optional[int] = Field(description="Line number where the issue was found")
    issue_type: str = Field(description="Type of issue: 'question', 'suggestion', 'nitpick', 'error', 'praise'")
    severity: str = Field(description="Severity of the issue: 'low', 'medium', 'high'")
    description: str = Field(description="Description of the issue")
    suggestion: Optional[str] = Field(None, description="Suggestion to fix the issue")
    confidence: float = Field(default=1.0, description="Confidence level of the issue detection (0.0 to 1.0)")
    guideline_violation: Optional[str] = Field(None, description="Reference to violated guideline if applicable")


class PRComment(BaseModel):
    """Represents a comment to be added to a PR."""
    content: str = Field(description="Content of the comment")
    file_path: Optional[str] = Field(None, description="File path where the comment should be added")
    line_number: Optional[int] = Field(None, description="Line number where the comment should be added")
    is_suggestion: bool = False
    comment_type: str = "inline"  # "inline", "body", "thread"
    commit_id: Optional[str] = None
    comment_id: Optional[str] = None


class PullRequest(BaseModel):
    """Represents a pull request."""
    pr_number: int
    title: str
    description: Optional[str] = None
    author: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    base_branch: str
    head_branch: str
    repository: str
    changes: List[FileChange] = Field(default_factory=list)
    comments: List[PRComment] = Field(default_factory=list)


class PRReviewState(BaseModel):
    """Represents the state of the PR review process."""
    pr_number: int
    repository: str
    pr_info: Optional[PullRequest] = None
    repository_info: Optional[RepositoryInfo] = None
    file_changes: List[FileChange] = Field(default_factory=list)
    complete_files: Dict[str, str] = Field(default_factory=dict)
    repository_context: Dict[str, Any] = Field(default_factory=dict)
    review_guidelines: Optional[GuidelinesInfo] = None
    pr_description_analysis: Dict[str, Any] = Field(default_factory=dict)
    linked_issues: List[IssueInfo] = Field(default_factory=list)
    detected_issues: List[PRIssue] = Field(default_factory=list)
    generated_comments: List[PRComment] = Field(default_factory=list)
    existing_comments: List[PRComment] = Field(default_factory=list)
    added_comments: List[PRComment] = Field(default_factory=list)
    approved: bool = False
    errors: List[Dict[str, Any]] = Field(default_factory=list)
