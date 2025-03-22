from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class FileChange(BaseModel):
    """Represents a file change in a PR."""
    filename: str
    status: str = Field(description="Status of the file: added, modified, deleted, etc.")
    patch: Optional[str] = Field(None, description="The actual diff content")
    additions: int = 0
    deletions: int = 0


class PRComment(BaseModel):
    """Represents a comment to be added to a PR."""
    path: str = Field(description="File path where the comment should be added")
    line: int = Field(description="Line number where the comment should be added")
    body: str = Field(description="Content of the comment")
    commit_id: Optional[str] = None
    comment_id: Optional[int] = None  # Used when retrieving existing comments


class PullRequest(BaseModel):
    """Represents a pull request."""
    pr_number: int
    title: str
    description: Optional[str] = None
    author: str
    created_at: datetime | None
    updated_at: datetime | None = None
    base_branch: str
    head_branch: str
    repository: str
    changes: List[FileChange] = Field(default_factory=list)
    comments: List[PRComment] = Field(default_factory=list)


class PRReviewState(BaseModel):
    """Represents the state of the PR review process."""
    pull_request: PullRequest
    analyzed_files: List[str] = Field(default_factory=list)
    detected_issues: List[Dict[str, Any]] = Field(default_factory=list)
    comments_to_add: List[PRComment] = Field(default_factory=list)
    comments_added: List[PRComment] = Field(default_factory=list)
    completed: bool = False
    error: Optional[str] = None
