#!/usr/bin/env python3
import asyncio
import typer
from typing import Optional
import os
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .utils.logging_utils import setup_logging
from .services.github_service import GitHubService
from .services.llm_service import LLMService
from .core.pr_review_agent import PRReviewAgent
from .models.pr_models import PRReviewState

app = typer.Typer(help="PR Review Agent CLI")
console = Console()

@app.command()
def review(
    pr: int = typer.Argument(..., help="PR number to review"),
    repo: str = typer.Option(None, help="Repository in the format 'owner/repo'"),
    model: str = typer.Option("mistral-openorca", help="Ollama model to use"),
    ollama_url: str = typer.Option("http://localhost:11434", help="Ollama API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """Review a GitHub pull request using LLM analysis."""
    # Set up logging with more detailed output for verbose mode
    logger = setup_logging(level="DEBUG" if verbose else "INFO", include_module=verbose)
    
    # Initialize services
    github_service = GitHubService(repository=repo)
    
    # Ensure the Ollama URL is properly formatted for the API
    if not ollama_url.endswith("/api/generate"):
        if ollama_url.endswith("/"):
            ollama_url = f"{ollama_url}api/generate"
        else:
            ollama_url = f"{ollama_url}/api/generate"
    
    llm_service = LLMService(api_url=ollama_url, model=model)
    
    # Initialize agent
    agent = PRReviewAgent(github_service, llm_service)
    
    # Display initial info
    console.print(Panel(f"PR Review Agent", title="Starting", subtitle="Powered by LangGraph"))
    console.print(f"Reviewing PR #{pr} in repository [bold]{repo}[/bold]")
    console.print(f"Using LLM model: [bold]{model}[/bold] via Ollama\n")
    
    try:
        # Run the agent
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Reviewing PR...", total=None)
            
            # Run the review process
            result = asyncio.run(agent.review_pr(pr))
            
            progress.update(task, completed=True, description="PR review completed")
        
        # Display results
        if result.get('error'):
            console.print(f"[bold red]Error:[/bold red] {result['error']}")
        else:
            console.print(f"\n[bold green]PR Review completed successfully![/bold green]")
            
            # Extract data from the result dictionary
            file_changes = result.get('file_changes', [])
            complete_files = result.get('complete_files', {})
            detected_issues = result.get('detected_issues', [])
            added_comments = result.get('added_comments', [])
            
            # Calculate analyzed files
            analyzed_file_paths = set()
            for change in file_changes:
                if hasattr(change, 'filename'):
                    analyzed_file_paths.add(change.filename)
                elif isinstance(change, dict) and 'filename' in change:
                    analyzed_file_paths.add(change['filename'])
            
            # Add complete files to analyzed files
            if isinstance(complete_files, dict):
                analyzed_file_paths.update(complete_files.keys())
            
            # Print summary information
            console.print(f"Analyzed {len(analyzed_file_paths)} files")
            
            # Print the list of analyzed files
            if analyzed_file_paths:
                console.print("\n[bold]Files analyzed:[/bold]")
                for file_path in sorted(analyzed_file_paths):
                    console.print(f"- {file_path}")
            
            console.print(f"\nFound {len(detected_issues)} potential issues")
            console.print(f"Added {len(added_comments)} comments to the PR")
            
            if added_comments:
                console.print("\n[bold]Comments added:[/bold]")
                for i, comment in enumerate(added_comments, 1):
                    if hasattr(comment, 'file_path') and hasattr(comment, 'line_number'):
                        console.print(f"{i}. {comment.file_path}:{comment.line_number}")
                    elif isinstance(comment, dict):
                        file_path = comment.get('file_path', comment.get('path', 'Unknown file'))
                        line_number = comment.get('line_number', comment.get('line', 'Unknown line'))
                        console.print(f"{i}. {file_path}:{line_number}")
                    else:
                        console.print(f"{i}. Unknown location")
    
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def check_ollama():
    """Check if Ollama is running with the required model."""
    from langchain_ollama import OllamaEndpoint
    import requests
    
    console.print("Checking Ollama installation...")
    
    try:
        # Check if Ollama is running
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            console.print("[bold red]Error:[/bold red] Ollama is not running properly.")
            console.print("Please ensure Ollama is installed and running.")
            console.print("See https://github.com/ollama/ollama for installation instructions.")
            return
        
        # Check for available models
        models = response.json().get("models", [])
        model_names = [model.get("name") for model in models]
        
        console.print(f"[bold green]Ollama is running![/bold green]")
        console.print(f"Available models: {', '.join(model_names) or 'None'}")
        
        # Check for mistral-openorca
        if "mistral-openorca" not in model_names:
            console.print("[bold yellow]Warning:[/bold yellow] 'mistral-openorca' model is not available.")
            console.print("To pull the model, run: ollama pull mistral-openorca")
        else:
            console.print("[bold green]'mistral-openorca' model is available![/bold green]")
    
    except requests.RequestException:
        console.print("[bold red]Error:[/bold red] Could not connect to Ollama API.")
        console.print("Please ensure Ollama is installed and running.")
        console.print("See https://github.com/ollama/ollama for installation instructions.")

@app.command()
def check_gh_cli():
    """Check if GitHub CLI is installed and authenticated."""
    import subprocess
    
    console.print("Checking GitHub CLI installation...")
    
    try:
        # Check if GitHub CLI is installed
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            console.print("[bold red]Error:[/bold red] GitHub CLI is not installed.")
            console.print("Please install GitHub CLI from https://cli.github.com/")
            return
        
        version = result.stdout.strip().split('\n')[0]
        console.print(f"[bold green]GitHub CLI is installed![/bold green] {version}")
        
        # Check if authenticated
        auth_result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if auth_result.returncode != 0:
            console.print("[bold yellow]Warning:[/bold yellow] Not authenticated with GitHub CLI.")
            console.print("Please run 'gh auth login' to authenticate.")
        else:
            console.print("[bold green]Authenticated with GitHub CLI![/bold green]")
    
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] GitHub CLI is not installed.")
        console.print("Please install GitHub CLI from https://cli.github.com/")

if __name__ == "__main__":
    app()
