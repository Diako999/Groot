"""Groot CLI — `python -m groot.cli chat` to talk to the local model."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown

from groot import speaker
from groot.audio_io import SAMPLE_RATE, record_seconds
from groot.config import load_config
from groot.conversation import GrootSession
from groot.ollama_client import OllamaError

app = typer.Typer(add_completion=False)
console = Console()

ENROLLMENT_SAMPLES = 5
ENROLLMENT_SECONDS = 3.0


@app.command()
def chat():
    """Start an interactive local chat session with Groot."""
    config = load_config()
    session = GrootSession(config)

    if not session.client.is_reachable():
        console.print(
            f"[red]Can't reach Ollama at {config.ollama_host}.[/red] "
            "Is it installed and running? Try: [bold]ollama serve[/bold]"
        )
        raise typer.Exit(1)

    console.print(f"[bold cyan]Groot[/bold cyan] — model: {config.model}")
    console.print("Type 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            user_input = console.input("[bold green]you[/bold green] > ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]bye.[/dim]")
            raise typer.Exit(0)

        if user_input.strip().lower() in {"exit", "quit"}:
            console.print("[dim]bye.[/dim]")
            raise typer.Exit(0)
        if not user_input.strip():
            continue

        console.print("[bold magenta]groot[/bold magenta] > ", end="")
        try:
            for chunk in session.turn(user_input):
                console.print(chunk, end="")
        except OllamaError as e:
            console.print(f"\n[red]{e}[/red]")
            continue

        console.print()


@app.command()
def enroll():
    """Record a few samples of your voice to enroll for speaker verification."""
    console.print(
        f"[bold cyan]Groot[/bold cyan] voice enrollment — say [bold]\"Hey Groot\"[/bold] "
        f"{ENROLLMENT_SAMPLES} times, {ENROLLMENT_SECONDS:.0f}s each.\n"
    )
    clips = []
    for i in range(1, ENROLLMENT_SAMPLES + 1):
        console.input(f"[bold green]({i}/{ENROLLMENT_SAMPLES})[/bold green] Press Enter, then say it > ")
        console.print("[dim]recording...[/dim]")
        clips.append(record_seconds(ENROLLMENT_SECONDS))
        console.print("[dim]got it.[/dim]\n")

    speaker.enroll_from_audio(clips, SAMPLE_RATE)
    console.print(f"[bold cyan]Voiceprint saved to {speaker.VOICEPRINT_FILE}[/bold cyan]")


@app.command()
def listen():
    """Always-on: listen for "Hey Groot", verify it's you, then chat by voice."""
    from groot.listen import listen as _listen

    _listen()


if __name__ == "__main__":
    app()
