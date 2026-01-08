# MyManus

A Python coding agent powered by DeepSeek and Docker Sandbox.

## Features

- **Autonomous Coding:** Generates and executes Python code based on user prompts.
- **Sandboxed Execution:** Runs code safely inside a persistent **Docker** container.
- **Stateful Environment:** Variables and files are preserved throughout the session.
- **Web Interface:** Includes a modern, terminal-style web console with real-time streaming feedback.
- **CLI Mode:** Offers a rich command-line interface for direct interaction.

## Prerequisites

1.  **Python 3.12+**
2.  **Docker** (Desktop or OrbStack) must be installed and running.
3.  **Local Image:** Ensure you have the `python:3.10.17-alpine3.21` image (or update `sandbox_mcp.py` to use another image present locally).
    ```bash
    # Verify image presence
    docker images python:3.10.17-alpine3.21
    ```

## Setup

1.  **Clone/Download the project.**
2.  **Environment Variables:**
    Create a `.env` file in the `mymanus` directory:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and add your API keys:
    ```ini
    DEEPSEEK_API_KEY=sk-your-key
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    MODEL_ID=deepseek-ai/DeepSeek-V3
    ```
3.  **Install Dependencies:**
    Using `uv` (recommended):
    ```bash
    uv sync
    ```

## Usage

### CLI Mode (Command Line)

Run the agent directly in your terminal:

```bash
uv run main.py
```

### Web Console (UI)

To launch the full-featured web interface:

1.  Start the backend server:
    ```bash
    uv run server.py
    ```
2.  Open your browser at [http://localhost:8000](http://localhost:8000).

    The web interface provides real-time streaming logs of the agent's thought process and execution results.

## Project Structure

- `agent.py`: Core ManusAgent logic (LLM interaction).
- `sandbox_mcp.py`: **Docker-based MCP Server**. Handles container lifecycle and command execution.
- `server.py`: FastAPI backend server.
- `main.py`: CLI entry point.
- `web/`: Frontend assets.
