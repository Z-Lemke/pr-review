from typing import Dict, List, Any, Annotated, TypedDict, Literal
from langgraph.graph import StateGraph, END
from ..models.pr_models import PRReviewState, PullRequest, PRComment
from ..services.github_service import GitHubService
from ..services.llm_service import LLMService
import logging

logger = logging.getLogger(__name__)

class PRReviewAgent:
    """Pull Request Review Agent built with LangGraph."""

    def __init__(self, github_service: GitHubService, llm_service: LLMService):
        """
        Initialize the PR Review Agent.
        
        Args:
            github_service: Service for interacting with GitHub
            llm_service: Service for interacting with LLM
        """
        self.github_service = github_service
        self.llm_service = llm_service
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for PR review."""
        # Define the graph
        graph = StateGraph(PRReviewState)
        
        # Add nodes to the graph
        graph.add_node("fetch_pr_info", self.fetch_pr_info)
        graph.add_node("fetch_pr_diff", self.fetch_pr_diff)
        graph.add_node("analyze_diff", self.analyze_diff)
        graph.add_node("generate_comments", self.generate_comments)
        graph.add_node("add_comments", self.add_comments)
        
        # Define the edges
        graph.add_edge("fetch_pr_info", "fetch_pr_diff")
        graph.add_edge("fetch_pr_diff", "analyze_diff")
        graph.add_edge("analyze_diff", "generate_comments")
        graph.add_edge("generate_comments", "add_comments")
        graph.add_edge("add_comments", END)
        
        # Set the entry point
        graph.set_entry_point("fetch_pr_info")
        
        return graph.compile()
    
    async def fetch_pr_info(self, state: PRReviewState) -> PRReviewState:
        """Fetch PR information from GitHub."""
        logger.info(f"Fetching PR information for PR #{state.pull_request.pr_number}")
        try:
            pr = self.github_service.get_pull_request(state.pull_request.pr_number)
            return PRReviewState(
                pull_request=pr,
                analyzed_files=state.analyzed_files,
                detected_issues=state.detected_issues,
                comments_to_add=state.comments_to_add,
                comments_added=state.comments_added,
                completed=False,
                error=None
            )
        except Exception as e:
            logger.error(f"Error fetching PR info: {str(e)}")
            return PRReviewState(
                pull_request=state.pull_request,
                analyzed_files=state.analyzed_files,
                detected_issues=state.detected_issues,
                comments_to_add=state.comments_to_add,
                comments_added=state.comments_added,
                completed=True,
                error=f"Error fetching PR info: {str(e)}"
            )
    
    async def fetch_pr_diff(self, state: PRReviewState) -> PRReviewState:
        """Fetch PR diff from GitHub."""
        logger.info(f"Fetching PR diff for PR #{state.pull_request.pr_number}")
        try:
            changes = self.github_service.get_pr_diff(state.pull_request.pr_number)
            
            # Update the PR with the changes
            updated_pr = state.pull_request.copy(update={"changes": changes})
            
            return PRReviewState(
                pull_request=updated_pr,
                analyzed_files=state.analyzed_files,
                detected_issues=state.detected_issues,
                comments_to_add=state.comments_to_add,
                comments_added=state.comments_added,
                completed=False,
                error=None
            )
        except Exception as e:
            logger.error(f"Error fetching PR diff: {str(e)}")
            return PRReviewState(
                pull_request=state.pull_request,
                analyzed_files=state.analyzed_files,
                detected_issues=state.detected_issues,
                comments_to_add=state.comments_to_add,
                comments_added=state.comments_added,
                completed=True,
                error=f"Error fetching PR diff: {str(e)}"
            )
    
    async def analyze_diff(self, state: PRReviewState) -> PRReviewState:
        """Analyze the PR diff for issues."""
        logger.info(f"Analyzing PR diff for PR #{state.pull_request.pr_number}")
        
        all_issues = []
        analyzed_files = state.analyzed_files.copy()
        
        for file_change in state.pull_request.changes:
            # Skip files that have already been analyzed or have no diff
            if file_change.filename in analyzed_files or not file_change.patch:
                continue
                
            logger.info(f"Analyzing file: {file_change.filename}")
            
            # Analyze the diff
            issues = self.llm_service.analyze_diff(file_change.filename, file_change.patch)
            
            # Add file-specific issues to the total list
            for issue in issues:
                issue["file"] = file_change.filename
                all_issues.append(issue)
            
            # Mark the file as analyzed
            analyzed_files.append(file_change.filename)
        
        return PRReviewState(
            pull_request=state.pull_request,
            analyzed_files=analyzed_files,
            detected_issues=state.detected_issues + all_issues,
            comments_to_add=state.comments_to_add,
            comments_added=state.comments_added,
            completed=False,
            error=None
        )
    
    async def generate_comments(self, state: PRReviewState) -> PRReviewState:
        """Generate PR comments from the detected issues."""
        logger.info(f"Generating comments for PR #{state.pull_request.pr_number}")
        
        # Group issues by file
        issues_by_file = {}
        for issue in state.detected_issues:
            file_path = issue.get("file", "")
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
        
        # Generate comments for each file
        all_comments = state.comments_to_add.copy()
        
        for file_path, issues in issues_by_file.items():
            comments = self.llm_service.generate_pr_comments(issues, file_path)
            
            for comment_data in comments:
                all_comments.append(PRComment(**comment_data))
        
        return PRReviewState(
            pull_request=state.pull_request,
            analyzed_files=state.analyzed_files,
            detected_issues=state.detected_issues,
            comments_to_add=all_comments,
            comments_added=state.comments_added,
            completed=False,
            error=None
        )
    
    async def add_comments(self, state: PRReviewState) -> PRReviewState:
        """Add comments to the PR."""
        logger.info(f"Adding comments to PR #{state.pull_request.pr_number}")
        
        added_comments = state.comments_added.copy()
        
        for comment in state.comments_to_add:
            # Skip comments that have already been added
            if any(c.path == comment.path and c.line == comment.line and c.body == comment.body for c in added_comments):
                continue
                
            try:
                # Add the comment to GitHub
                added_comment = self.github_service.add_pr_comment(
                    state.pull_request.pr_number, 
                    comment
                )
                
                # Add to the list of added comments
                added_comments.append(added_comment)
                
                logger.info(f"Added comment to {comment.path} at line {comment.line}")
            except Exception as e:
                logger.error(f"Error adding comment: {str(e)}")
        
        return PRReviewState(
            pull_request=state.pull_request,
            analyzed_files=state.analyzed_files,
            detected_issues=state.detected_issues,
            comments_to_add=state.comments_to_add,
            comments_added=added_comments,
            completed=True,
            error=None
        )
    
    async def review_pr(self, pr_number: int) -> PRReviewState:
        """
        Review a pull request.
        
        Args:
            pr_number: The PR number to review
            
        Returns:
            The final state of the review process
        """
        # Initialize the state
        initial_state = PRReviewState(
            pull_request=PullRequest(
                pr_number=pr_number,
                title="",
                author="",
                created_at=None,
                base_branch="",
                head_branch="",
                repository=self.github_service.repository
            )
        )
        
        # Run the workflow
        result = await self.graph.ainvoke(initial_state)
        
        return result
