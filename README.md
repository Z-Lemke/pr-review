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

## Future Enhancements

- Integration with MCPs (Jira, GitHub API, etc.)
- Enhanced PR considerations (security, test coverage, etc.)
- Advanced review capabilities (comment resolution, PR approval, etc.)
