from typing import List, Dict, Any, Optional
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
import json

class LLMService:
    """Service for interacting with language models."""

    def __init__(self, model_name: str = "mistral-openorca", base_url: str = "http://localhost:11434"):
        """
        Initialize the LLM service.
        
        Args:
            model_name: The model name to use with Ollama
            base_url: URL for the Ollama API
        """
        self.model_name = model_name
        self.base_url = base_url
        self.llm = ChatOllama(
            model=model_name,
            base_url=base_url
        )
    
    def _create_chat_model(self, temperature: float = 0.1):
        """Create a chat model with specific temperature."""
        return self.llm.with_config({"temperature": temperature})

    def analyze_diff(self, file_path: str, diff_content: str) -> List[Dict[str, Any]]:
        """
        Analyze a diff for potential issues.
        
        Args:
            file_path: The path of the file being analyzed
            diff_content: The diff content to analyze
            
        Returns:
            List of issues found in the diff
        """
        system_prompt = """You are a senior software engineer reviewing a code change in a pull request.
Your task is to analyze the diff of a file and identify potential issues, bugs, or improvements.
Focus on:

1. Code quality issues
2. Potential bugs or edge cases
3. Performance concerns
4. Security vulnerabilities
5. Missing tests or documentation
6. Requirements implementation issues

For each issue you find, provide:
1. The line number in the new code
2. A description of the issue
3. The severity (high, medium, low)
4. A suggestion for how to fix it

Respond in JSON format with a list of issues:
[
  {
    "line_number": 123,
    "description": "Description of the issue",
    "severity": "high|medium|low",
    "suggestion": "How to fix the issue"
  }
]

If no issues are found, return an empty list: []
"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"File: {file_path}\n\nDiff:\n{diff_content}")
        ])
        
        chat_model = self._create_chat_model()
        
        try:
            chain = prompt | chat_model | StrOutputParser()
            response = chain.invoke({})
            
            # Extract JSON from the response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                json_str = response.strip()
                
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback in case the LLM doesn't return valid JSON
            return [{"line_number": 0, "description": f"Failed to parse response: {response[:100]}...", "severity": "low", "suggestion": "Please fix the issue manually"}]
        except Exception as e:
            return [{"line_number": 0, "description": f"Error analyzing diff: {str(e)}", "severity": "low", "suggestion": "Please review the diff manually"}]

    def generate_pr_comments(self, issues: List[Dict[str, Any]], file_path: str) -> List[Dict[str, Any]]:
        """
        Generate PR comments from issues.
        
        Args:
            issues: List of issues found in the diff
            file_path: The path of the file with issues
            
        Returns:
            List of PR comments to add
        """
        if not issues:
            return []
            
        system_prompt = """You are a helpful and constructive PR reviewer. 
Your task is to convert analysis issues into constructive PR comments.
Make sure your comments are:
1. Specific and actionable
2. Polite and constructive 
3. Clear about the impact of the issue
4. Helpful with a suggested solution

Format the comment in Markdown.
"""
        comments = []
        
        for issue in issues:
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Issue:\n{json.dumps(issue, indent=2)}\n\nCreate a PR comment for this issue.")
            ])
            
            chat_model = self._create_chat_model(temperature=0.2)
            chain = prompt | chat_model | StrOutputParser()
            
            try:
                comment_text = chain.invoke({})
                comments.append({
                    "path": file_path,
                    "line": issue.get("line_number", 1),
                    "body": comment_text.strip()
                })
            except Exception as e:
                # Fallback to simpler comment if generation fails
                comments.append({
                    "path": file_path,
                    "line": issue.get("line_number", 1),
                    "body": f"**{issue.get('severity', 'medium').upper()} Issue**: {issue.get('description')}\n\n**Suggestion**: {issue.get('suggestion')}"
                })
                
        return comments
