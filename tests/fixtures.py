"""Test fixtures for PR review agent tests."""

from src.models.pr_models import (
    PullRequest,
    FileChange,
    RepositoryInfo,
    GuidelinesInfo,
    DocumentInfo,
    IssueInfo
)
from typing import List, Dict, Any

# Sample PR data
sample_pr_data = {
    "number": 123,
    "title": "Add new feature",
    "description": "This PR adds a new feature that does something cool.",
    "author": "test-user",
    "base_branch": "main",
    "head_branch": "feature-branch",
    "url": "https://github.com/org/repo/pull/123"
}

# Sample file changes
sample_file_changes = [
    FileChange(
        filename="src/main.py",
        status="modified",
        additions=10,
        deletions=5,
        patch="@@ -1,5 +1,10 @@\n def main():\n-    print('Hello')\n+    print('Hello, World!')\n+    do_something()\n+\n+def do_something():\n+    print('Doing something')\n"
    ),
    FileChange(
        filename="tests/test_main.py",
        status="added",
        additions=15,
        deletions=0,
        patch="@@ -0,0 +1,15 @@\n+import unittest\n+from src.main import main, do_something\n+\n+class TestMain(unittest.TestCase):\n+    def test_main(self):\n+        # Test main function\n+        self.assertTrue(True)\n+\n+    def test_do_something(self):\n+        # Test do_something function\n+        self.assertTrue(True)\n+\n+if __name__ == '__main__':\n+    unittest.main()\n+"
    )
]

# Sample repository info
sample_repository_info = RepositoryInfo(
    name="test-repo",
    owner="test-org",
    description="A test repository for PR review agent",
    default_branch="main",
    language="Python",
    topics=["testing", "automation"],
    has_issues=True,
    has_wiki=True,
    has_projects=True,
    license="MIT",
    created_at="2023-01-01T00:00:00Z",
    updated_at="2023-06-01T00:00:00Z",
    pushed_at="2023-06-01T00:00:00Z",
    size=1024,
    stargazers_count=10,
    watchers_count=5,
    forks_count=2,
    open_issues_count=3,
    subscribers_count=4,
    network_count=2,
    url="https://github.com/test-org/test-repo"
)

# Sample guidelines info
sample_guidelines_info = GuidelinesInfo(
    content="""# Contributing Guidelines
    
## Code Style
- Follow PEP 8 for Python code
- Use 4 spaces for indentation
- Maximum line length is 100 characters
- Use docstrings for all public functions, classes, and methods
    
## Testing
- Write unit tests for all new code
- Maintain test coverage above 80%
- Run tests before submitting a PR
    
## Pull Requests
- Keep PRs small and focused
- Include a clear description of changes
- Reference any related issues
- Update documentation as needed
""",
    source="CONTRIBUTING.md",
    parsed_rules=[
        "Follow PEP 8 for Python code",
        "Use 4 spaces for indentation",
        "Maximum line length is 100 characters",
        "Use docstrings for all public functions, classes, and methods",
        "Write unit tests for all new code",
        "Maintain test coverage above 80%",
        "Run tests before submitting a PR",
        "Keep PRs small and focused",
        "Include a clear description of changes",
        "Reference any related issues",
        "Update documentation as needed"
    ]
)

# Sample documentation info
sample_documentation_info = [
    DocumentInfo(
        path="README.md",
        content="""# Test Repository
        
This is a test repository for the PR review agent.

## Installation
```
pip install -r requirements.txt
```

## Usage
```python
from src.main import main

main()
```

## Contributing
Please see CONTRIBUTING.md for guidelines.
""",
        type="README"
    ),
    DocumentInfo(
        path="docs/API.md",
        content="""# API Documentation

## Main Module
- `main()`: Entry point function
- `do_something()`: Does something important
""",
        type="API"
    )
]

# Sample issue info
sample_issue_info = [
    IssueInfo(
        number=1,
        title="Bug in main function",
        body="There's a bug in the main function that needs to be fixed.",
        state="open",
        author="test-user",
        labels=["bug", "priority-high"],
        created_at="2023-05-01T00:00:00Z",
        updated_at="2023-05-02T00:00:00Z",
        url="https://github.com/test-org/test-repo/issues/1"
    ),
    IssueInfo(
        number=2,
        title="Add new feature",
        body="We should add a new feature to do something cool.",
        state="open",
        author="another-user",
        labels=["enhancement", "priority-medium"],
        created_at="2023-05-10T00:00:00Z",
        updated_at="2023-05-11T00:00:00Z",
        url="https://github.com/test-org/test-repo/issues/2"
    )
]

# Sample repository structure
sample_repository_structure = {
    "src": {
        "main.py": "file",
        "utils": {
            "helpers.py": "file",
            "__init__.py": "file"
        },
        "__init__.py": "file"
    },
    "tests": {
        "test_main.py": "file",
        "test_utils": {
            "test_helpers.py": "file",
            "__init__.py": "file"
        },
        "__init__.py": "file"
    },
    "docs": {
        "API.md": "file",
        "USAGE.md": "file"
    },
    "README.md": "file",
    "CONTRIBUTING.md": "file",
    "requirements.txt": "file"
}

# Sample complete file content
sample_complete_file_content = {
    "src/main.py": """def main():
    print('Hello, World!')
    do_something()

def do_something():
    print('Doing something')
""",
    "tests/test_main.py": """import unittest
from src.main import main, do_something

class TestMain(unittest.TestCase):
    def test_main(self):
        # Test main function
        self.assertTrue(True)

    def test_do_something(self):
        # Test do_something function
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
"""
}

# Sample LLM responses
sample_diff_analysis_response = """```json
[
    {
        "line_number": 3,
        "description": "Added a call to do_something() without error handling",
        "severity": "medium",
        "suggestion": "Consider adding error handling around the do_something() call"
    },
    {
        "line_number": 6,
        "description": "New function lacks docstring",
        "severity": "low",
        "suggestion": "Add a docstring to explain what do_something() does"
    }
]
```"""

sample_diff_analysis_with_context_response = """```json
[
    {
        "line": 3,
        "description": "Added a call to do_something() without error handling",
        "severity": "medium",
        "suggestion": "Consider adding error handling around the do_something() call",
        "guideline_violation": "Use docstrings for all public functions, classes, and methods"
    },
    {
        "line": 6,
        "description": "New function lacks docstring",
        "severity": "low",
        "suggestion": "Add a docstring to explain what do_something() does",
        "guideline_violation": "Use docstrings for all public functions, classes, and methods"
    }
]
```"""

sample_pr_description_analysis_response = """```json
{
    "summary": "This PR adds a new feature that does something cool.",
    "key_changes": [
        "Added do_something() function",
        "Modified main() to call the new function",
        "Added tests for the new functionality"
    ],
    "potential_issues": [
        "No error handling in the new function",
        "Missing docstrings for the new function"
    ],
    "suggested_focus_areas": [
        "Error handling",
        "Documentation",
        "Test coverage"
    ]
}
```"""
