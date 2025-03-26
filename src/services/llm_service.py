import json
import requests
from typing import List, Dict, Any, Optional
import logging
import os

from ..models.pr_models import GuidelinesInfo, DocumentInfo

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with LLMs to analyze code."""
    
    def __init__(self, api_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LLM service.
        
        Args:
            api_url: URL for the LLM API (default: environment variable LLM_API_URL)
            model: Model to use (default: environment variable LLM_MODEL)
        """
        self.api_url = api_url or os.environ.get("LLM_API_URL", "http://localhost:11434/api/generate")
        self.model = model or os.environ.get("LLM_MODEL", "mistral")
    
    def analyze_diff(self, file_path: str, diff_content: str) -> List[Dict[str, Any]]:
        """
        Analyze the diff content of a file and identify potential issues.
        
        Args:
            file_path: Path to the file being analyzed
            diff_content: Diff content to analyze
            
        Returns:
            List of issues found, each with line number, description, and suggestion
        """
        # Construct prompt for the LLM
        prompt = self._construct_diff_analysis_prompt(file_path, diff_content)
        
        # Get response from LLM
        response = self._query_llm(prompt)
        
        # Parse the response to extract issues
        issues = self._parse_diff_analysis_response(response)
        
        return issues
    
    def analyze_diff_with_context(self, file_path: str, diff_content: str, 
                                  full_file_content: Optional[str] = None,
                                  guidelines: Optional[GuidelinesInfo] = None,
                                  repository_docs: Optional[List[DocumentInfo]] = None) -> List[Dict[str, Any]]:
        """
        Analyze the diff content with additional context.
        
        Args:
            file_path: Path to the file being analyzed
            diff_content: Diff content to analyze
            full_file_content: Full content of the file (optional)
            guidelines: Repository guidelines (optional)
            repository_docs: Repository documentation (optional)
            
        Returns:
            List of issues found, each with line number, description, and suggestion
        """
        # Construct prompt for the LLM with additional context
        prompt = self._construct_diff_analysis_prompt_with_context(
            file_path, 
            diff_content, 
            full_file_content, 
            guidelines, 
            repository_docs
        )
        
        # Get response from LLM
        response = self._query_llm(prompt)
        
        # Parse the response to extract issues
        issues = self._parse_diff_analysis_response(response)
        
        return issues
    
    def analyze_pr_description(self, pr_description: str) -> Dict[str, Any]:
        """
        Analyze the PR description to extract key information.
        
        Args:
            pr_description: The PR description
            
        Returns:
            Dictionary with analysis results
        """
        # Construct prompt for the LLM
        prompt = self._construct_pr_description_analysis_prompt(pr_description)
        
        # Get response from LLM
        response = self._query_llm(prompt)
        
        # Parse the response to extract analysis
        analysis = self._parse_pr_description_analysis(response)
        
        return analysis
    
    def _construct_diff_analysis_prompt(self, file_path: str, diff_content: str) -> str:
        """
        Construct a prompt for diff analysis.
        
        Args:
            file_path: Path to the file being analyzed
            diff_content: Diff content to analyze
            
        Returns:
            Prompt for the LLM
        """
        prompt = f"""
You are a code review assistant. Analyze the following diff for potential issues.
Focus on:
1. Bugs or logical errors
2. Security vulnerabilities
3. Performance issues
4. Code style and best practices
5. Potential edge cases

File: {file_path}

Diff:
```
{diff_content}
```

Provide your analysis in the following JSON format:
{{
  "issues": [
    {{
      "line": <line_number>,
      "type": "<question|suggestion|nitpick|error|praise>",
      "description": "<clear description of the issue>",
      "suggestion": "<specific suggestion to fix the issue>",
      "severity": "<high|medium|low>"
    }}
  ]
}}

If no issues are found, return an empty issues array.
"""
        return prompt
    
    def _construct_diff_analysis_prompt_with_context(
        self, 
        file_path: str, 
        diff_content: str, 
        full_file_content: Optional[str] = None,
        guidelines: Optional[GuidelinesInfo] = None,
        repository_docs: Optional[List[DocumentInfo]] = None
    ) -> str:
        """
        Construct a prompt for analyzing a diff with additional context.
        
        Args:
            file_path: Path to the file being analyzed
            diff_content: Diff content to analyze
            full_file_content: Full content of the file being analyzed
            guidelines: Repository guidelines to consider
            repository_docs: Additional repository documentation
            
        Returns:
            Prompt for the LLM
        """
        prompt = f"""
You are a code reviewer analyzing changes in a Pull Request. Review the following code diff and provide feedback.

File: {file_path}

Complete file content:
```
{full_file_content[:2000] if full_file_content else "Not available"}
```

Changes (diff):
```
{diff_content}
```

"""
        # Add guidelines if available
        if guidelines and hasattr(guidelines, 'content'):
            prompt += f"""
Consider these guidelines when reviewing:
{guidelines.content}

"""
        
        # Add relevant repository documentation if available
        if repository_docs:
            # First, find the most relevant documentation files for this PR
            relevant_docs = []
            
            # Extract file extension and path components for matching
            file_ext = file_path.split('.')[-1] if '.' in file_path else ''
            path_components = file_path.split('/')
            
            # Score each doc based on relevance to the current file
            scored_docs = []
            for doc in repository_docs:
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
            
            # Take the top 3 most relevant docs
            relevant_docs = [doc for doc, _ in scored_docs[:3]]
            
            # If we didn't find any relevant docs, just take the first few
            if not relevant_docs and repository_docs:
                relevant_docs = repository_docs[:3]
            
            prompt += "\nRepository Documentation:\n"
            
            for doc in relevant_docs:
                doc_type = doc.type if hasattr(doc, 'type') and doc.type else "Documentation"
                doc_path = doc.path if hasattr(doc, 'path') else "Unknown"
                doc_content = doc.content if hasattr(doc, 'content') else ""
                
                # Truncate content to keep prompt size reasonable
                truncated_content = doc_content[:800] + "..." if len(doc_content) > 800 else doc_content
                
                prompt += f"""
{doc_type} ({doc_path}):
```
{truncated_content}
```
"""
        
        prompt += """
Provide your analysis in the following JSON format:
{
  "issues": [
    {
      "line": <line_number>,
      "type": "<question|suggestion|nitpick|error|praise>",
      "description": "<clear description of the issue>",
      "suggestion": "<suggested fix if applicable>",
      "severity": "<high|medium|low>",
      "confidence": <float between 0 and 1>,
      "guideline_violation": "<reference to violated guideline if applicable>"
    },
    ...
  ]
}

Focus on:
1. Logic errors
2. Performance issues
3. Security concerns
4. Code style
5. Documentation
6. Edge cases
7. Tests

If no issues are found, return an empty issues array.
"""
        return prompt
    
    def _construct_pr_description_analysis_prompt(self, pr_description: str) -> str:
        """
        Construct a prompt for PR description analysis.
        
        Args:
            pr_description: The PR description
            
        Returns:
            Prompt for the LLM
        """
        prompt = f"""
You are a code review assistant. Analyze the following pull request description to extract key information.
Focus on:
1. Purpose of the PR
2. Changes made
3. Testing done
4. Areas that need reviewer attention
5. Related issues or tickets

PR Description:
```
{pr_description}
```

Provide your analysis in the following JSON format:
{{
  "purpose": "<summary of the PR purpose>",
  "changes": ["<list of main changes>"],
  "testing_done": "<description of testing done or null>",
  "attention_areas": ["<areas needing reviewer attention>"],
  "completeness": "<assessment of PR description completeness: high|medium|low>"
}}
"""
        return prompt
    
    def _format_list(self, items: List[str]) -> str:
        """
        Format a list of items as a numbered list.
        
        Args:
            items: List of items to format
            
        Returns:
            Formatted list as a string
        """
        if not items:
            return "No specific rules found."
        
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
    
    def _query_llm(self, prompt: str) -> str:
        """
        Query the LLM with a prompt.
        
        Args:
            prompt: Prompt for the LLM
            
        Returns:
            Response from the LLM
        """
        try:
            # For Ollama API
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            
            # Ensure the API URL is correct for Ollama
            api_url = self.api_url
            if not api_url.endswith("/api/generate"):
                # If the URL doesn't end with /api/generate, append it
                if api_url.endswith("/"):
                    api_url = f"{api_url}api/generate"
                else:
                    api_url = f"{api_url}/api/generate"
            
            logger.info(f"Querying LLM at {api_url} with model {self.model}")
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            
            response_data = response.json()
            return response_data.get("response", "")
        except Exception as e:
            logger.error(f"Error querying LLM: {str(e)}")
            return ""
    
    def _parse_diff_analysis_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse the LLM response to extract issues.
        
        Args:
            response: Response from the LLM
            
        Returns:
            List of issues found, each with line number, description, and suggestion
        """
        try:
            # Log the raw response for debugging
            logger.debug(f"Raw LLM response: {response}")
            
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in LLM response")
                return []
            
            json_str = response[json_start:json_end]
            logger.debug(f"Extracted JSON string: {json_str}")
            
            # Clean up the JSON string to handle common issues
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}. Attempting to clean up.")
                # Try to fix common JSON issues
                json_str = json_str.replace("'", "\"")  # Replace single quotes with double quotes
                json_str = json_str.replace("\\", "\\\\")  # Escape backslashes
                
                # Try again with cleaned JSON
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON even after cleanup.")
                    return []
            
            logger.debug(f"Parsed JSON data: {data}")
            
            # Handle various possible response formats
            if isinstance(data, dict):
                issues = data.get("issues", [])
                if not issues and "analysis" in data:
                    issues = data.get("analysis", {}).get("issues", [])
            elif isinstance(data, list):
                # If the LLM directly returned a list of issues
                issues = data
            else:
                logger.warning(f"Unexpected data format: {type(data)}")
                return []
                
            logger.debug(f"Extracted issues: {issues}")
            
            # Make sure issues is a list
            if not isinstance(issues, list):
                logger.warning(f"Issues is not a list: {type(issues)}")
                if isinstance(issues, dict):
                    issues = [issues]  # Convert single issue dict to list
                else:
                    return []
            
            # Normalize each issue to ensure it has all required fields
            normalized_issues = []
            for issue in issues:
                if not isinstance(issue, dict):
                    logger.warning(f"Skipping non-dict issue: {issue}")
                    continue
                    
                # Create a normalized issue with all required fields
                normalized_issue = {
                    "line": issue.get("line", issue.get("line_number", 1)),
                    "description": issue.get("description", issue.get("comment", issue.get("message", ""))),
                    "suggestion": issue.get("suggestion", issue.get("fix", "")),
                    "severity": issue.get("severity", "low"),
                    "type": issue.get("type", issue.get("issue_type", "suggestion")),
                    "confidence": float(issue.get("confidence", 1.0)),
                }
                
                # Validate that type is one of the allowed values
                allowed_types = ["question", "suggestion", "nitpick", "error", "praise"]
                if normalized_issue["type"] not in allowed_types:
                    normalized_issue["type"] = "suggestion"  # Default fallback
                
                normalized_issues.append(normalized_issue)
                logger.debug(f"Normalized issue: {normalized_issue}")
            
            return normalized_issues
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            logger.error(f"Response that caused the error: {response}")
            return []
    
    def _parse_pr_description_analysis(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response to extract PR description analysis.
        
        Args:
            response: Response from the LLM
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning("No JSON found in LLM response")
                return {
                    "purpose": "Could not extract purpose",
                    "changes": [],
                    "testing_done": None,
                    "attention_areas": [],
                    "completeness": "low"
                }
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            return {
                "purpose": data.get("purpose", ""),
                "changes": data.get("changes", []),
                "testing_done": data.get("testing_done"),
                "attention_areas": data.get("attention_areas", []),
                "completeness": data.get("completeness", "low")
            }
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            return {
                "purpose": "Error parsing response",
                "changes": [],
                "testing_done": None,
                "attention_areas": [],
                "completeness": "low"
            }
