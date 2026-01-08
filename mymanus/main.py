import asyncio
import os
import sys
from rich.console import Console
from rich.prompt import Prompt
from dotenv import load_dotenv
from agent import ManusAgent

# Load environment variables
load_dotenv()

console = Console()

async def main():
    console.print("[bold magenta]Welcome to MyManus (Microsandbox Edition)[/bold magenta]")
    console.print("Type 'exit' or 'quit' to stop.")
    
    # Check for API Key
    if not os.getenv("DEEPSEEK_API_KEY"):
        console.print("[bold red]ERROR: DEEPSEEK_API_KEY is not set.[/bold red]")
        console.print("Please create a .env file with your key.")

    agent = ManusAgent()

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]What would you like me to do?[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("Goodbye!")
                break
                
            if not user_input.strip():
                continue

            console.print(f"[bold green]Manus Agent received task:[/bold green] {user_input}")
            
            # Consume the generator
            async for event in agent.run(user_input):
                event_type = event.get("type")
                if event_type == "status":
                    console.print(f"[dim]{event.get('message')}[/dim]")
                elif event_type == "code":
                    console.print("[bold blue]Generated Code:[/bold blue]")
                    console.print(event.get("content"), style="cyan")
                elif event_type == "output":
                    console.print("[bold]Execution Result:[/bold]")
                    console.print(event.get("content"), style="white on black")
                elif event_type == "answer":
                    console.print("\n[bold yellow]Agent Answer:[/bold yellow]")
                    console.print(event.get("content"))
                elif event_type == "error":
                    console.print(f"[red]Error: {event.get('message')}[/red]")
                elif event_type == "success":
                    console.print(f"[bold green]{event.get('message')}[/bold green]")

        except KeyboardInterrupt:
            console.print("\nExiting...")
            break
        except Exception as e:
            console.print(f"[red]An error occurred: {e}[/red]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
