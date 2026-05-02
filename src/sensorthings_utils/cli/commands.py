"""CLI command handlers."""

# standard
import os
import shutil
from pathlib import Path
from typing import Optional
import subprocess
# external
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich import print as rprint

# internal
from .menu import _setup_credentials
from ..paths import DEPLOY_DIR, START_SCRIPT, STOP_SCRIPT

# Create typer app and console
app = typer.Typer(
    help="st-utils CLI - SensorThings Utilities",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


def _validate(
    file: Optional[Path] = typer.Argument(None, help="Config file to validate (optional).")
):
    """Validate sensor configuration files."""
    from sensorthings_utils.sensor_things.extensions import SensorConfig
    
    if file:
        validation_files = [str(file)]
    else:
        validation_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(".")
            for f in files
            if (f.endswith((".yaml", "yml")) and not f.startswith("template"))
        ]

    if not validation_files:
        console.print("[yellow]No YAML files found to validate.[/yellow]")
        return

    console.print(f"\n[bold]Validating {len(validation_files)} file(s)...[/bold]\n")
    
    all_valid = True
    for f in validation_files:
        result, errors = SensorConfig(f).check_validity()
        if errors:
            all_valid = False
            console.print(f"[red]❌ {f}[/red]")
            for e in errors:
                console.print(f"  [red]{e}[/red]")
        else:
            console.print(f"[green]✓ {f}[/green]")
    
    if all_valid:
        console.print("\n[bold green]All files are valid![/bold green]")
    else:
        console.print("\n[bold red]Some files have validation errors.[/bold red]")


def _get_bash() -> str:
    """
    Find bash executable, preferring Git Bash over WSL on Windows.
    
    Git Bash and WSL use different drive mount prefixes:
      - Git Bash: /d/path
      - WSL:      /mnt/d/path
    Prefer Git Bash so path conversion stays consistent.
    Returns the path to the bash executable.
    """
    # Common Git Bash locations
    git_bash_candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "bash.exe",
    ]
    for candidate in git_bash_candidates:
        if candidate.exists():
            return str(candidate)

    # Fall back to whatever bash is on PATH
    bash = shutil.which("bash")
    if bash:
        return bash

    raise RuntimeError(
        "bash not found. Install Git Bash (https://git-scm.com) or WSL to run st-utils on Windows."
    )


def _get_drive_mount_prefix(bash: str) -> str:
    """
    Detect the drive mount prefix used by the given bash installation.
    
    Runs 'bash -c pwd' from a known drive root to detect whether
    drives are mounted at /mnt/d or /d (Git Bash vs WSL).
    Falls back to /mnt/ if detection fails.
    """
    try:
        # Simpler and more reliable: just check if /mnt/c exists in this bash
        probe = subprocess.run(
            [bash, "-c", "test -d /mnt/c && echo mnt || test -d /c && echo root || echo mnt"],
            capture_output=True, text=True, timeout=5
        )
        prefix = probe.stdout.strip()
        return "/mnt/" if prefix == "mnt" else "/"
    except Exception:
        return "/mnt/"  # safe default (WSL)


def to_bash_path(path: Path, bash: Optional[str] = None) -> str:
    """
    Convert a Windows path to a POSIX path for the detected bash environment.
    
    Handles both Git Bash (/d/path) and WSL (/mnt/d/path) automatically.
    On non-Windows systems, returns the path unchanged.
    """
    p = Path(path).resolve()

    if os.name != "nt":
        return str(p)

    bash = bash or _get_bash()
    prefix = _get_drive_mount_prefix(bash)
    drive = p.drive[0].lower()        # 'D:' → 'd'
    path_no_drive = str(p)[2:]        # remove 'D:'

    return prefix + drive + path_no_drive.replace("\\", "/")


def require_bash() -> str:
    """
    Ensure bash is available on Windows and return its path.
    Raises RuntimeError with a helpful message if not found.
    """
    return _get_bash()


def _push_available(
    private: bool = typer.Option(
        False, "--private", help="Start with authentication (requires tomcat-users.xml)."
    ),
    frost_endpoint: Optional[str] = typer.Option(
        None, "--frost-endpoint", help="Change default FROST server URL."
    ),
    exclude: Optional[str] = typer.Option(
        None, "--exclude", help="Pass a list of sensor MAC addresses to exclude from the stream."
    ),
):
    """Start the STU instance."""
    
    mode = "private" if private else "public"
    console.print(f"[bold]Starting STU instance in {mode} mode...[/bold]")

    # Cross-platform handling: Windows requires bash + POSIX path conversion
    if os.name == "nt": # Windows-specific handling
        bash = require_bash()
        cmd = [bash, to_bash_path(START_SCRIPT, bash), mode]

    else:
        # macOS/Linux: execute directly
        cmd = [str(START_SCRIPT), mode]

    result = subprocess.run(
        cmd,
        cwd=DEPLOY_DIR,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"Failed to start STU: {result.stderr}")
    else:
        if private:
            console.print("System starting with authentication at http://localhost:8080/st-utils")
        else:
            console.print("System starting (public access) at http://localhost:8080/st-utils")


def _stop_instance():
    """Stop the STU instance."""
    
    console.print("[bold]Stopping STU instance...[/bold]")

    # Cross-platform command handling (Windows, macOS, Linux)
    if os.name == "nt":
        bash = require_bash()
        cmd = [bash, to_bash_path(STOP_SCRIPT, bash)]
    else:
        cmd = [str(STOP_SCRIPT)]

    # Avoid shell=True: run command directly for consistent cross-platform behavior (no extra shell layer or parsing issues)
    result = subprocess.run(
            cmd, 
            cwd=DEPLOY_DIR,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        console.print(f"[red]Failed to stop STU:[/red] {result.stderr}")
    else:
        console.print("[green]✓ STU instance stopped successfully[/green]")


def _generate_config(
    sensor_model: str = typer.Argument(
        ..., help="Sensor model: milesight.am103l, milesight.am308l, or netatmo.nws03"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (defaults to sensor_configs/{sensor_id}.yaml)"
    ),
):
    """Generate sensor configuration file from template."""
    from .config_generator import generate_config_from_template
    from sensorthings_utils.transformers.types import SupportedSensors
    
    try:
        sensor_model_enum = SupportedSensors(sensor_model)
    except ValueError:
        console.print(f"[bold red]Error:[/bold red] Unsupported sensor model: {sensor_model}")
        console.print("Supported models: milesight.am103l, milesight.am308l, netatmo.nws03")
        raise typer.Exit(1)
    
    # Collect user inputs with rich prompts
    console.print(Panel.fit(
        f"[bold]Generating configuration for {sensor_model_enum.value}[/bold]",
        border_style="blue"
    ))
    
    sensor_id = Prompt.ask("Sensor ID/Name", default="").strip()
    if not sensor_id:
        console.print("[bold red]Error:[/bold red] Sensor ID is required")
        raise typer.Exit(1)
    
    console.print("\n[bold]Thing Configuration:[/bold]")
    thing_name = Prompt.ask("Thing name", default="").strip()
    if not thing_name:
        console.print("[bold red]Error:[/bold red] Thing name is required")
        raise typer.Exit(1)
    
    thing_description = Prompt.ask("Thing description", default="").strip()
    if not thing_description:
        console.print("[bold red]Error:[/bold red] Thing description is required")
        raise typer.Exit(1)
    
    console.print("\n[bold]Location Configuration:[/bold]")
    location_name = Prompt.ask("Location name", default="").strip()
    if not location_name:
        console.print("[bold red]Error:[/bold red] Location name is required")
        raise typer.Exit(1)
    
    location_description = Prompt.ask("Location description", default="").strip()
    if not location_description:
        console.print("[bold red]Error:[/bold red] Location description is required")
        raise typer.Exit(1)
    
    try:
        longitude = float(Prompt.ask("Longitude", default="").strip())
        latitude = float(Prompt.ask("Latitude", default="").strip())
    except ValueError:
        console.print("[bold red]Error:[/bold red] Longitude and latitude must be valid numbers")
        raise typer.Exit(1)
    
    # Generate config
    try:
        output_path = generate_config_from_template(
            sensor_model=sensor_model_enum,
            sensor_id=sensor_id,
            thing_name=thing_name,
            thing_description=thing_description,
            location_name=location_name,
            location_description=location_description,
            longitude=longitude,
            latitude=latitude,
            output_path=output_path,
        )
        console.print(f"\n[bold green]✓ Configuration generated successfully:[/bold green] {output_path}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  1. Review the configuration file")
        console.print(f"  2. Validate it using: [cyan]stu validate {output_path}[/cyan]")
    except Exception as e:
        console.print(f"\n[bold red]Error generating configuration:[/bold red] {e}")
        import traceback
        console.print_exception()
        raise typer.Exit(1)


def _setup(
    all: bool = typer.Option(False, "--all", help="Setup all credential types."),
    frost: bool = typer.Option(False, "--frost", help="Setup FROST credentials."),
    postgres: bool = typer.Option(False, "--postgres", help="Setup PostgreSQL credentials."),
    mqtt: bool = typer.Option(False, "--mqtt", help="Setup MQTT credentials."),
    tomcat: bool = typer.Option(False, "--tomcat", help="Setup Tomcat users (webapp authentication)."),
    token: bool = typer.Option(False, "--token", help="Setup a token file (freeform JSON)."),
):
    """Interactive application, sensor and credentil manager."""
    # Create a simple args-like object for backward compatibility
    class Args:
        def __init__(self):
            self.all = all
            self.frost = frost
            self.postgres = postgres
            self.mqtt = mqtt
            self.tomcat = tomcat
            self.token = token
    
    args = Args()
    _setup_credentials(args)


# Register commands
app.command(name="start")(_push_available)
app.command(name="stop")(_stop_instance)
app.command(name="setup")(_setup)
app.command(name="validate")(_validate)
app.command(name="generate-config")(_generate_config)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
