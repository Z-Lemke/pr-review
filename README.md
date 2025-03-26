# PR Review Agent

An LLM-powered agent that automatically reviews Pull Requests.

## Features (MVP)

- Analyze PR diffs to identify potential issues
- Create PR comments for questionable code or potential improvements
- Uses Ollama with Mistral-OpenOrca model for local inference

## Prerequisites

- Python 3.9+
- [Ollama](https://github.com/ollama/ollama) installed and running locally with the `mistral-openorca` model
- GitHub CLI (for interacting with PRs)

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install and configure GitHub CLI:
   ```bash
   # macOS (using Homebrew)
   brew install gh

   # Windows
   winget install --id GitHub.cli

   # Linux (Debian/Ubuntu)
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update
   sudo apt install gh
   ```

4. Authenticate with GitHub:
   ```bash
   gh auth login
   ```
   Follow the interactive prompts to authenticate. You'll need to select:
   - GitHub.com (not enterprise)
   - HTTPS protocol
   - Authenticate with your GitHub credentials
   - Choose your preferred authentication method (browser or token)

5. Make sure Ollama is running with mistral-openorca model:
   ```
   ollama pull mistral-openorca
   ollama serve
   ```

## Usage

Example:
```bash
python -m src.main review 1 --repo username/repository
```

You can also check if your environment is properly configured:
```bash
# Check GitHub CLI installation and authentication
python -m src.main check_gh_cli

# Check Ollama installation and available models
python -m src.main check_ollama
```

## Architecture

The PR Review Agent is built using LangGraph, providing a flexible and extensible architecture:

- **Core**: Contains the main agent logic and state management
- **Models**: Data models and schemas
- **Services**: External integrations (GitHub, Ollama, etc.)
- **Utils**: Utility functions for common tasks

### Project Structure

```
pr-review/
├── src/
│   ├── core/
│   │   └── pr_review_agent.py       # Main agent implementation using LangGraph
│   ├── models/
│   │   └── pr_models.py             # Pydantic models for PR data structures
│   ├── services/
│   │   ├── github_service.py        # GitHub API integration
│   │   └── llm_service.py           # LLM integration (Ollama/Mistral)
│   ├── utils/
│   │   └── logging_utils.py         # Logging configuration
│   └── main.py                      # CLI entry point
├── tests/                           # Unit tests
├── requirements.txt                 # Dependencies
└── README.md                        # Documentation
```

### Design Patterns and Architecture

#### 1. Service-Oriented Architecture

The project follows a service-oriented architecture where each external integration is encapsulated in a dedicated service class:

- **GitHubService**: Handles all GitHub API interactions, including fetching PR information, diffs, and adding comments
- **LLMService**: Manages interactions with the LLM (Mistral-OpenOrca via Ollama), including prompt construction and response parsing

This separation of concerns allows for:
- Easy replacement of services (e.g., switching from GitHub to GitLab)
- Clear boundaries between different parts of the system
- Simplified testing through mocking

#### 2. State Management with LangGraph

The agent uses LangGraph for workflow orchestration, which provides:
- A declarative way to define the PR review workflow
- Clear state transitions between different stages of the review process
- Persistent state management throughout the review process

The workflow consists of the following steps:
1. Fetch PR information
2. Fetch PR diff
3. Analyze diff using LLM
4. Generate comments based on analysis
5. Add comments to the PR

#### 3. Data Models with Pydantic

All data structures are defined as Pydantic models, providing:
- Runtime type checking
- Automatic validation
- Clear documentation of data structures
- Serialization/deserialization capabilities

### Data Flow

The PR review process follows this data flow:

1. **Input**: PR number and repository information from CLI
2. **PR Information Retrieval**:
   - The GitHubService fetches basic PR information (title, description, author)
   - The PR diff is retrieved to identify code changes
3. **Analysis**:
   - The LLMService analyzes each file change in the diff
   - Issues are identified and structured as PRIssue objects
4. **Comment Generation**:
   - For each issue, a PR comment is generated with appropriate context
   - Comments include the file path, line number, and suggestion
5. **Comment Submission**:
   - Comments are added to the PR via the GitHub API
   - Line-specific comments are added using the GitHub REST API
   - Regular PR comments are used as a fallback if line-specific comments fail

### Key Components

#### PRReviewAgent

The central component that orchestrates the entire review process. It:
- Builds and manages the LangGraph workflow
- Coordinates between different services
- Maintains the state throughout the review process

#### PRReviewState

A Pydantic model that represents the current state of the review process, including:
- Pull request information
- Analyzed files
- Detected issues
- Comments to add
- Comments that have been added
- Completion status
- Error information

#### GitHub Integration

The GitHubService uses the GitHub CLI (`gh`) to interact with GitHub. Key features:
- Authentication through GitHub CLI credentials
- PR information retrieval
- Diff analysis
- Adding both line-specific and regular PR comments
- Debugging support with curl command printing

#### LLM Integration

The LLMService uses LangChain to interact with the LLM. Key features:
- Dynamic prompt construction based on file content
- Structured output parsing
- Error handling for invalid responses
- Configurable model parameters

### Error Handling

The system implements robust error handling:
- Service-level error handling with appropriate fallbacks
- State tracking of errors throughout the workflow
- Graceful degradation (e.g., falling back to regular PR comments if line comments fail)
- Detailed logging for debugging

### Testing Strategy

The project uses pytest for testing with:
- Unit tests for individual components
- Mock objects for external dependencies
- Fixtures for common test data
- Async testing support for the LangGraph workflow

## Configuration

The agent can be configured through environment variables or command-line arguments:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--repo` | GitHub repository in format `owner/repo` | Current directory's remote |
| `--model` | LLM model to use | `mistral-openorca` |
| `--verbose` | Enable verbose logging | `False` |

## Future Enhancements

- Integration with MCPs (Jira, GitHub API, etc.)
- Enhanced PR considerations (security, test coverage, etc.)
- Advanced review capabilities (comment resolution, PR approval, etc.)
- Support for additional LLM providers
- Customizable review policies
- Performance optimizations for large PRs
