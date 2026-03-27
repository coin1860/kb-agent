"""
kb-cli CLI entrypoint.

Usage:
    kb-cli [--data-folder PATH]
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match a supported version.*")

import typer
from rich.console import Console

app = typer.Typer(
    name="kb-cli",
    help="KB-Cli Agent — LLM-driven interactive task execution shell.",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    data_folder: Optional[Path] = typer.Option(
        None,
        "--data-folder",
        help="Override the data folder path (skills/, output/, python_code/ derived from this).",
        envvar="KB_AGENT_DATA_FOLDER",
    ),
) -> None:
    """Launch the KB-Cli interactive agent shell."""
    # 1. Load settings
    import kb_agent.config as config
    from kb_agent.config import load_settings

    load_settings()
    settings = config.settings

    if not settings:
        console.print("[bold red]Error:[/bold red] Settings not configured. "
                      "Please set KB_AGENT_LLM_API_KEY in your .env file.")
        raise typer.Exit(1)

    # 2. Override data_folder if provided
    if data_folder is not None:
        settings.data_folder = data_folder  # type: ignore[assignment]
        settings._compute_paths()

    # 3. Validate required LLM settings
    if not settings.llm_api_key and not settings.llm_base_url:
        console.print("[bold red]Error:[/bold red] LLM not configured. "
                      "Please set KB_AGENT_LLM_API_KEY and KB_AGENT_LLM_BASE_URL.")
        raise typer.Exit(1)

    # 4. Build LLM
    try:
        from langchain_openai import ChatOpenAI
        model_name = settings.llm_model or "gpt-4o"
        if model_name.startswith("groq-com/") or model_name.startswith("groq/"):
            model_name = model_name.split("/", 1)[-1]
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else "local"
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=str(settings.llm_base_url) if settings.llm_base_url else None,
            model=model_name,
            temperature=0.2,
            timeout=60,
        )
    except Exception as e:
        console.print(f"[bold red]Failed to initialize LLM:[/bold red] {e}")
        raise typer.Exit(1)

    # 5. Ensure directories exist
    # settings.*_path fields are already Path objects after load_settings()/_compute_paths()
    # Using them directly avoids TypeError when the value is None or still an OptionInfo default.
    def _to_path(val) -> Path:
        """Safely coerce a settings path field to a Path, falling back to cwd."""
        if val is None or not hasattr(val, '__fspath__') and not isinstance(val, (str, Path)):
            raise typer.BadParameter(
                "Could not determine required paths. Please configure data_folder in kb-agent settings."
            )
        return Path(val)

    try:
        skills_path = _to_path(settings.skills_path)
        output_path = _to_path(settings.output_path)
        python_code_path = _to_path(settings.python_code_path)
        input_path = _to_path(settings.input_path)
        temp_path = _to_path(settings.temp_path)
    except Exception as e:
        console.print(f"[bold red]Error resolving paths:[/bold red] {e}")
        console.print("[dim]Hint: set data_folder in kb-agent TUI settings or use --data-folder flag.[/dim]")
        raise typer.Exit(1)

    skills_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    python_code_path.mkdir(parents=True, exist_ok=True)
    input_path.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir(parents=True, exist_ok=True)

    # 6. Load skills
    from kb_agent.skill.loader import load_skills
    skills = load_skills(skills_path)
    if not skills:
        console.print(f"[dim]No skills found in {skills_path}[/dim]")

    # 7. Launch shell — derive effective_data_folder without touching settings.data_folder directly
    #    (it may be None if the user hasn't set it; skills_path.parent is always a safe parent)
    from kb_agent.skill.shell import SkillShell
    _df = settings.data_folder
    if _df is not None and isinstance(_df, (str, Path)) and not isinstance(_df, type):
        effective_data_folder = Path(_df)
    else:
        effective_data_folder = skills_path.parent

    shell = SkillShell(
        skills=skills,
        output_path=output_path,
        python_code_path=python_code_path,
        llm=llm,
        console=console,
        input_path=input_path,
        temp_path=temp_path,
    )
    shell.start(effective_data_folder)


if __name__ == "__main__":
    app()


def run():
    """Entry point for the kb-cli console script.

    pyproject.toml [project.scripts] must point to a plain callable.
    Calling app() ensures Typer processes sys.argv correctly and injects
    properly parsed values (not raw OptionInfo defaults) into main().
    """
    app()
