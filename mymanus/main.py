import asyncio
import os
import sys
from rich.console import Console
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.panel import Panel
from dotenv import load_dotenv
from agent import ManusAgent

# Load environment variables
load_dotenv()

console = Console()

async def main():
    console.print(Panel.fit("[bold magenta]Welcome to MyManus (LangGraph Edition)[/bold magenta]", border_style="magenta"))
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
            current_thought = ""
            
            async for event in agent.run(user_input):
                event_type = event.get("type")
                
                if event_type == "thought":
                    # Stream thought content
                    content = event.get("content")
                    current_thought += content
                    # We could print streaming, but for simplicity let's just print chunks or use a live display
                    # For CLI, let's just print simple chunks to avoid messing up the terminal
                    console.print(content, end="", style="dim")
                    
                elif event_type == "status":
                    # New line before status
                    if current_thought:
                        console.print() 
                        current_thought = ""
                    console.print(f"[yellow]>> {event.get('message')}[/yellow]")
                    
                elif event_type == "output":
                    if current_thought:
                        console.print()
                        current_thought = ""
                    console.print(Panel(event.get("content"), title="Tool Output", border_style="blue"))
                    
                elif event_type == "preview":
                    console.print(f"[bold green]File Preview:[/bold green] {event.get('content')}")
                    
                elif event_type == "error":
                    console.print(f"[bold red]Error: {event.get('message')}[/bold red]")
                    
                elif event_type == "success":
                    if current_thought:
                        console.print()
                    console.print(Panel(event.get("message"), style="bold green"))

            # End of run
            if current_thought:
                console.print()

        except KeyboardInterrupt:
            console.print("\nExiting...")
            break
        except Exception as e:
            console.print(f"[red]An error occurred: {e}[/red]")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass