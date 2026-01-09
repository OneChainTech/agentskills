# MyManus

A Python coding agent powered by DeepSeek and E2B Firecracker Sandbox.

## Features

- **Autonomous Coding:** Generates and executes Python code based on user prompts.
- **Secure Sandboxing:** Runs code inside secure, ephemeral **E2B Firecracker MicroVMs**.
- **Stateful Environment:** Variables and files are preserved throughout the session.
- **Web Interface:** Includes a modern, terminal-style web console with real-time streaming feedback and file previews.
- **CLI Mode:** Offers a rich command-line interface for direct interaction.

## Prerequisites

1.  **Python 3.12+**
2.  **E2B API Key**: Get one at [e2b.dev](https://e2b.dev).
3.  **DeepSeek API Key**: Or compatible OpenAI-format provider.

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
    E2B_API_KEY=e2b_...
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

    The web interface provides real-time streaming logs of the agent's thought process, execution results, and visualizations.

## Project Structure

- `agent.py`: Core ManusAgent logic (LLM interaction).
- `sandbox_e2b.py`: **E2B-based MCP Server**. Handles remote sandbox lifecycle and command execution.
- `server.py`: FastAPI backend server.
- `main.py`: CLI entry point.
- `web/`: Frontend assets.