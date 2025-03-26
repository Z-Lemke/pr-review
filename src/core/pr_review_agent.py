from typing import Dict, List, Any, Optional
import logging
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END, START

from ..models.pr_models import (
    PRReviewState, 
    PullRequest, 
    PRComment, 
    PRIssue,
    RepositoryInfo,
    GuidelinesInfo,
    DocumentInfo,
    IssueInfo
)
from ..services.github_service import GitHubService
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

class PRReviewAgent:
    """Agent for reviewing GitHub PRs using LLMs."""
    
    def __init__(
        self,
        github_service: Optional[GitHubService] = None,
        llm_service: Optional[LLMService] = None,
        repository: Optional[str] = None,
        github_token: Optional[str] = None
    ):
        """
        Initialize the PR Review Agent.
        
        Args:
            github_service: GitHub service instance (optional)
            llm_service: LLM service instance (optional)
            repository: Repository in the format 'owner/repo' (optional)
            github_token: GitHub token for authentication (optional)
        """
        self.github_service = github_service or GitHubService(repository=repository, token=github_token)
        self.llm_service = llm_service or LLMService()
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for PR review."""
        # Define the workflow graph
        workflow = StateGraph(PRReviewState)
        
        # Add nodes to the workflow
        workflow.add_node("fetch_pr_info", self.fetch_pr_info)
        workflow.add_node("fetch_repository_info", self.fetch_repository_info)
        workflow.add_node("fetch_repository_guidelines", self.fetch_repository_guidelines)
        workflow.add_node("fetch_pr_diff", self.fetch_pr_diff)
        workflow.add_node("fetch_complete_files", self.fetch_complete_files)
        workflow.add_node("fetch_repository_docs", self.fetch_repository_docs)
        workflow.add_node("analyze_pr_description", self.analyze_pr_description)
        workflow.add_node("fetch_linked_issues", self.fetch_linked_issues)
        workflow.add_node("analyze_diff", self.analyze_diff)
        workflow.add_node("generate_comments", self.generate_comments)
        workflow.add_node("add_comments", self.add_comments)
        
        # Define the edges of the workflow
        workflow.set_entry_point("fetch_pr_info")
        workflow.add_edge("fetch_pr_info", "fetch_repository_info")
        workflow.add_edge("fetch_repository_info", "fetch_repository_guidelines")
        workflow.add_edge("fetch_repository_guidelines", "fetch_pr_diff")
        workflow.add_edge("fetch_pr_diff", "fetch_complete_files")
        workflow.add_edge("fetch_complete_files", "fetch_repository_docs")
        workflow.add_edge("fetch_repository_docs", "analyze_pr_description")
        workflow.add_edge("analyze_pr_description", "fetch_linked_issues")
        workflow.add_edge("fetch_linked_issues", "analyze_diff")
        workflow.add_edge("analyze_diff", "generate_comments")
        workflow.add_edge("generate_comments", "add_comments")
        workflow.add_edge("add_comments", END)
        
        # Compile the workflow
        return workflow.compile()
    
    async def review_pr(self, pr_number: int, repository: Optional[str] = None) -> PRReviewState:
        """
        Review a pull request.
        
        Args:
            pr_number: The PR number
            repository: The repository in the format 'owner/repo', overrides the one set in constructor
            
        Returns:
            The final state of the PR review
        """
        # Initialize the state with proper default values
        initial_state = PRReviewState(
            pr_number=pr_number,
            repository=repository or self.github_service.repository,
            pr_info=None,
            repository_info=None,
            file_changes=[],
            complete_files={},
            repository_context={},
            review_guidelines=None,
            pr_description_analysis={},
            linked_issues=[],
            detected_issues=[],
            generated_comments=[],
            existing_comments=[],
            added_comments=[],
            approved=False,
            errors=[]
        )
        
        # Run the workflow
        config = RunnableConfig(recursion_limit=25)  # Set a recursion limit to prevent infinite loops
        result = await self.workflow.ainvoke(initial_state, config)
        
        return result
    
    async def fetch_pr_info(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch information about a pull request.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with PR information
        """
        logger.info(f"Fetching PR info for PR #{state.pr_number}")
        
        try:
            pull_request = self.github_service.get_pull_request(
                pr_number=state.pr_number,
                repository=state.repository
            )
            
            # Create a new state with the updated pr_info
            state_dict = state.model_dump()
            state_dict["pr_info"] = pull_request
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching PR info: {str(e)}")
            raise
    
    async def fetch_repository_info(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch information about the repository.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with repository information
        """
        # Use repository from state directly if pr_info is None
        repository = state.repository
        if state.pr_info:
            repository = state.pr_info.repository or repository
            
        logger.info(f"Fetching repository info for {repository}")
        
        try:
            repository_info = self.github_service.get_repository_info(
                repository=repository
            )
            
            # Create a new state with the updated repository_info
            state_dict = state.model_dump()
            state_dict["repository_info"] = repository_info
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching repository info: {str(e)}")
            # Continue with workflow even if repository info fetch fails
            return state
    
    async def fetch_repository_guidelines(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch repository guidelines.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with repository guidelines
        """
        # Use repository from state directly if pr_info is None
        repository = state.repository
        if state.pr_info:
            repository = state.pr_info.repository or repository
            
        logger.info(f"Fetching repository guidelines for {repository}")
        
        try:
            guidelines = self.github_service.get_repository_guidelines(
                repository=repository
            )
            
            # Create a new state with the updated guidelines
            state_dict = state.model_dump()
            state_dict["review_guidelines"] = guidelines
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching repository guidelines: {str(e)}")
            # Continue with workflow even if guidelines fetch fails
            return state
    
    async def fetch_pr_diff(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch the diff for a pull request.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with PR diff
        """
        pr_number = state.pr_number
        repository = state.repository
        
        if state.pr_info:
            pr_number = state.pr_info.pr_number or pr_number
            repository = state.pr_info.repository or repository
            
        logger.info(f"Fetching PR diff for PR #{pr_number}")
        
        try:
            file_changes = self.github_service.get_pr_diff(
                pr_number=pr_number,
                repository=repository
            )
            
            # Log the files being analyzed from the diff
            if file_changes:
                file_paths = []
                for change in file_changes:
                    # FileChange objects have a 'filename' attribute, not 'file_path'
                    if hasattr(change, 'filename'):
                        file_paths.append(change.filename)
                    elif isinstance(change, dict) and 'filename' in change:
                        file_paths.append(change['filename'])
                
                logger.info(f"Found {len(file_paths)} changed files in the PR diff")
                for file_path in file_paths:
                    logger.info(f"Analyzing changes in file: {file_path}")
            
            # Create a new state with the updated file_changes
            state_dict = state.model_dump()
            state_dict["file_changes"] = file_changes
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching PR diff: {str(e)}")
            # Continue with workflow even if diff fetch fails
            return state
            
    async def fetch_complete_files(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch complete file content for files in the PR.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with complete file content
        """
        pr_number = state.pr_number
        repository = state.repository
        
        if state.pr_info:
            pr_number = state.pr_info.pr_number or pr_number
            repository = state.pr_info.repository or repository
            
        logger.info(f"Fetching complete files for PR #{pr_number}")
        
        try:
            # Get the base branch from PR info
            base_branch = None
            if state.pr_info:
                base_branch = state.pr_info.base_branch
                
            # Get file paths from file_changes
            file_paths = []
            for change in state.file_changes:
                # FileChange objects have a 'filename' attribute, not 'file_path'
                if hasattr(change, 'filename'):
                    file_paths.append(change.filename)
                elif isinstance(change, dict) and 'filename' in change:
                    file_paths.append(change['filename'])
            
            # Log the files being fetched
            logger.info(f"Fetching complete content for {len(file_paths)} files")
            
            # Fetch complete files
            complete_files = {}
            for file_path in file_paths:
                logger.info(f"Fetching complete file: {file_path}")
                content = self.github_service.get_complete_file(
                    repository=repository,
                    file_path=file_path,
                    ref="HEAD"  # Get the latest version from the PR
                )
                if content:
                    complete_files[file_path] = content
            
            # Create a new state with the updated complete_files
            state_dict = state.model_dump()
            state_dict["complete_files"] = complete_files
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching complete files: {str(e)}")
            # Continue with workflow even if complete files fetch fails
            return state
    
    async def fetch_repository_docs(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch repository documentation by scanning the entire repository for markdown files.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with repository documentation
        """
        # Use repository from state directly if pr_info is None
        repository = state.repository
        if state.pr_info:
            repository = state.pr_info.repository or repository
            
        # Use base_branch from pr_info if available
        base_branch = None
        if state.pr_info:
            base_branch = state.pr_info.base_branch
            
        logger.info(f"Fetching repository docs for {repository}")
        
        try:
            # Get all markdown files from the repository
            docs = self.github_service.get_repository_docs(
                repository=repository,
                ref=base_branch
            )
            
            # Log the markdown files found
            logger.info(f"Found {len(docs)} markdown files in the repository")
            for doc in docs:
                logger.info(f"Adding context from markdown file: {doc.path}")
            
            # Create a new state with the updated repository_context
            state_dict = state.model_dump()
            repository_context = state_dict.get("repository_context", {})
            repository_context["docs"] = docs
            state_dict["repository_context"] = repository_context
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching repository docs: {str(e)}")
            # Continue with workflow even if docs fetch fails
            return state
    
    async def analyze_pr_description(self, state: PRReviewState) -> PRReviewState:
        """
        Analyze the PR description to extract key information.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with PR description analysis
        """
        logger.info(f"Analyzing PR description for PR #{state.pr_number}")
        
        try:
            # Skip if pr_info is None or has no description
            if not state.pr_info or not state.pr_info.description:
                # Skip analysis if there's no description
                return state
            
            analysis = self.llm_service.analyze_pr_description(
                pr_description=state.pr_info.description
            )
            
            # Create a new state with the updated pr_description_analysis
            state_dict = state.model_dump()
            state_dict["pr_description_analysis"] = analysis
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error analyzing PR description: {str(e)}")
            # Continue with workflow even if description analysis fails
            return state
    
    async def fetch_linked_issues(self, state: PRReviewState) -> PRReviewState:
        """
        Fetch issues linked to the PR.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with linked issues
        """
        logger.info(f"Fetching linked issues for PR #{state.pr_number}")
        
        try:
            # Skip if pr_info is None or has no description
            if not state.pr_info or not state.pr_info.description:
                # Skip if there's no description
                return state
            
            linked_issues = self.github_service.get_linked_issues(
                pr_description=state.pr_info.description
            )
            
            # Create a new state with the updated linked_issues
            state_dict = state.model_dump()
            state_dict["linked_issues"] = linked_issues
            return PRReviewState(**state_dict)
        except Exception as e:
            logger.error(f"Error fetching linked issues: {str(e)}")
            # Continue with workflow even if linked issues fetch fails
            return state
    
    async def analyze_diff(self, state: PRReviewState) -> PRReviewState:
        """
        Analyze the diff for a pull request.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with detected issues
        """
        logger.info(f"Analyzing diff for PR #{state.pr_number}")
        
        issues = []
        
        # Skip if pr_info is None or has no changes
        if not state.pr_info or not state.pr_info.changes:
            # Create a new state with empty detected_issues
            state_dict = state.model_dump()
            state_dict["detected_issues"] = issues
            return PRReviewState(**state_dict)
        
        # Get repository docs if available
        docs = state.repository_context.get("docs", [])
        logger.info(f"Using {len(docs)} markdown files for context")
        
        # Process each file change
        for file_change in state.pr_info.changes:
            # Skip files without patches
            if not file_change.patch:
                continue
            
            try:
                # Get the full file content if available
                full_content = state.complete_files.get(file_change.filename)
                
                # Get repository guidelines if available
                guidelines = state.review_guidelines
                
                # Prioritize markdown files that are relevant to this file
                # This helps ensure the LLM has the most relevant context
                relevant_docs = self._prioritize_relevant_docs(file_change.filename, docs)
                
                # Analyze the diff with context
                if full_content:
                    file_issues = self.llm_service.analyze_diff_with_context(
                        file_path=file_change.filename,
                        diff_content=file_change.patch,
                        full_file_content=full_content,
                        guidelines=guidelines,
                        repository_docs=relevant_docs
                    )
                else:
                    # Fallback to basic diff analysis if full content is not available
                    file_issues = self.llm_service.analyze_diff(
                        file_path=file_change.filename,
                        diff_content=file_change.patch
                    )
                
                # Log the issues for debugging
                logger.debug(f"LLM returned issues for {file_change.filename}: {file_issues}")
                
                # Convert to PRIssue objects
                for issue in file_issues:
                    try:
                        # Safely get the type field with a default value
                        if not isinstance(issue, dict):
                            logger.warning(f"Expected dict, got {type(issue)}: {issue}")
                            continue
                            
                        # Determine issue type based on available information
                        issue_type = issue.get("type")
                        if not issue_type:
                            # Default to suggestion if type is empty or missing
                            issue_type = "suggestion"
                        
                        # Make sure issue_type is one of the allowed values
                        allowed_types = ["question", "suggestion", "nitpick", "error", "praise"]
                        if issue_type not in allowed_types:
                            issue_type = "suggestion"  # Default fallback
                        
                        # Create the PRIssue object with safe access to all fields
                        pr_issue = PRIssue(
                            file_path=file_change.filename,
                            line_number=issue.get("line", issue.get("line_number", 1)),
                            description=issue.get("description", ""),
                            suggestion=issue.get("suggestion", ""),
                            severity=issue.get("severity", "low"),
                            guideline_violation=issue.get("guideline_violation"),
                            issue_type=issue_type,
                            confidence=issue.get("confidence", 1.0)
                        )
                        
                        issues.append(pr_issue)
                    except Exception as e:
                        logger.error(f"Error processing issue: {str(e)}")
            except Exception as e:
                logger.error(f"Error analyzing diff for {file_change.filename}: {str(e)}")
        
        # Create a new state with the updated detected_issues
        state_dict = state.model_dump()
        state_dict["detected_issues"] = issues
        return PRReviewState(**state_dict)
        
    def _prioritize_relevant_docs(self, file_path: str, docs: List[DocumentInfo]) -> List[DocumentInfo]:
        """
        Prioritize markdown files that are relevant to the file being changed.
        
        Args:
            file_path: Path to the file being changed
            docs: List of all markdown files in the repository
            
        Returns:
            List of markdown files prioritized by relevance
        """
        if not docs:
            return []
            
        # Extract file extension and path components for matching
        file_ext = file_path.split('.')[-1] if '.' in file_path else ''
        path_components = file_path.split('/')
        
        # Score each doc based on relevance to the current file
        scored_docs = []
        for doc in docs:
            if not hasattr(doc, 'path') or not hasattr(doc, 'content'):
                continue
                
            score = 0
            doc_path = doc.path.lower()
            doc_content = doc.content.lower()
            
            # Check if doc mentions this file path or components
            if file_path.lower() in doc_content:
                score += 10
            
            # Check if doc mentions the file extension
            if file_ext and file_ext.lower() in doc_content:
                score += 5
            
            # Check if doc is in the same directory
            for component in path_components:
                if component.lower() in doc_path:
                    score += 3
            
            # Prioritize certain types of docs
            if hasattr(doc, 'type'):
                doc_type = doc.type.lower() if doc.type else ""
                if "readme" in doc_type or "readme" in doc_path:
                    score += 8
                elif "architecture" in doc_type or "design" in doc_path:
                    score += 7
                elif "contributing" in doc_type:
                    score += 6
            
            scored_docs.append((doc, score))
        
        # Sort docs by relevance score (highest first)
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Return all docs, but prioritized by relevance
        return [doc for doc, _ in scored_docs]
    
    async def generate_comments(self, state: PRReviewState) -> PRReviewState:
        """
        Generate comments from the identified issues.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with generated comments
        """
        logger.info(f"Generating comments for PR #{state.pr_number}")
        
        comments = []
        
        for issue in state.detected_issues:
            # Format the comment content
            content = f"**{issue.severity.upper()}**: {issue.description}\n\n"
            
            if issue.suggestion:
                content += f"**Suggestion**: {issue.suggestion}"
            
            if issue.guideline_violation:
                content += f"\n\n**Guideline Violation**: {issue.guideline_violation}"
            
            # Create a comment
            comment = PRComment(
                file_path=issue.file_path,
                line_number=issue.line_number,
                content=content,
                comment_type="inline"
            )
            
            comments.append(comment)
        
        # Create a new state with the updated generated_comments
        state_dict = state.model_dump()
        state_dict["generated_comments"] = comments
        return PRReviewState(**state_dict)
    
    async def add_comments(self, state: PRReviewState) -> PRReviewState:
        """
        Add comments to the PR.
        
        Args:
            state: The current state
            
        Returns:
            Updated state with added comments
        """
        logger.info(f"Adding comments to PR #{state.pr_number}")
        
        added_comments = []
        
        # Use repository from state directly if pr_info is None
        repository = state.repository
        if state.pr_info:
            repository = state.pr_info.repository or repository
        
        for comment in state.generated_comments:
            try:
                added_comment = self.github_service.add_pr_comment(
                    pr_number=state.pr_number,
                    comment=comment,
                    repository=repository
                )
                
                added_comments.append(added_comment)
                logger.info(f"Added comment to {comment.file_path}:{comment.line_number}")
            except Exception as e:
                logger.error(f"Error adding comment: {str(e)}")
                # Continue with the next comment
                continue
        
        # Create a new state with the updated added_comments
        state_dict = state.model_dump()
        state_dict["added_comments"] = added_comments
        return PRReviewState(**state_dict)
