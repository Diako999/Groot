"""Groot CLI — `python -m groot.cli chat` to talk to the local model."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown

from groot.config import load_config
from groot.memory import MemoryStore
from groot.ollama_client import OllamaClient, OllamaError

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def chat():
    """Start an interactive local chat session with Groot."""
    config = load_config()
    client = OllamaClient(config)
    memory = MemoryStore(config)

    if not client.is_reachable():
        console.print(
            f"[red]Can't reach Ollama at {config.ollama_host}.[/red] "
            "Is it installed and running? Try: [bold]ollama serve[/bold]"
        )
        raise typer.Exit(1)

    console.print(f"[bold cyan]Groot[/bold cyan] — model: {config.model}")
    console.print("Type 'exit' or Ctrl+C to quit.\n")

    history: list[dict] = []

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

        history.append({"role": "user", "content": user_input})

        remembered = memory.query(user_input)
        messages_for_model = history
        if remembered:
            context_block = "\n".join(f"- {m}" for m in remembered)
            messages_for_model = [
                {
                    "role": "system",
                    "content": f"Relevant memory from past sessions:\n{context_block}",
                }
            ] + history

        console.print("[bold magenta]groot[/bold magenta] > ", end="")
        reply = ""
        try:
            for chunk in client.stream_chat(messages_for_model):
                console.print(chunk, end="")
                reply += chunk
        except OllamaError as e:
            console.print(f"\n[red]{e}[/red]")
            history.pop()
            continue

        console.print()
        history.append({"role": "assistant", "content": reply})
        memory.add(f"User: {user_input}", category="conversation")
        memory.add(f"Groot: {reply}", category="conversation")


if __name__ == "__main__":
    app()
