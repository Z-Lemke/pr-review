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

IMPORTANT: For each issue you find, you MUST identify the EXACT line number in the new code.
Look for lines starting with '+' in the diff and count them correctly.
The line number should correspond to the actual line in the file AFTER the changes are applied.

For each issue you find, provide:
1. The line_number in the new code (this is critical for in-line comments)
2. A suggestion for how to fix it

Respond in JSON format with a list of issues:
[
  {
    "line_number": 123,
    "suggestion": "Detailed explanation of the issue and how to fix it"
  }
]

If no issues are found, return an empty list: []
"""
        # Extract line numbers from the diff to help the LLM
        diff_lines = diff_content.split('\n')
        line_mapping = {}
        current_line = 0
        
        for line in diff_lines:
            if line.startswith('@@'):
                # Parse the @@ -a,b +c,d @@ line to get the starting line number
                try:
                    # Extract the +c,d part and then get c (starting line number)
                    plus_part = line.split('+')[1].split(' ')[0]
                    current_line = int(plus_part.split(',')[0])
                except (IndexError, ValueError):
                    current_line = 0
            elif line.startswith('+') and not line.startswith('+++'):
                # Map this line in the diff to the actual file line number
                line_mapping[len(line_mapping) + 1] = current_line
                current_line += 1
            elif line.startswith(' '):
                # Unchanged line
                current_line += 1
            # We don't increment for removed lines (starting with '-')
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"File: {file_path}\n\nDiff:\n{diff_content}\n\nLine mapping (diff line -> file line): {json.dumps(line_mapping)}")
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
                
            issues = json.loads(json_str)
            
            # Ensure all issues have valid line numbers and add file_path
            for issue in issues:
                if issue.get("line_number", 0) <= 0:
                    # If the LLM didn't provide a valid line number, set it to 1
                    issue["line_number"] = 1
                # Add the file path to each issue
                issue["file_path"] = file_path
            
            return issues
        except json.JSONDecodeError:
            # Fallback in case the LLM doesn't return valid JSON
            return [{"line_number": 1, "file_path": file_path, "suggestion": f"Failed to parse response: {response[:100]}..."}]
        except Exception as e:
            return [{"line_number": 1, "file_path": file_path, "suggestion": f"Error analyzing diff: {str(e)}"}]
