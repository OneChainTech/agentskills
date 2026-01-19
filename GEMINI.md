# Project Context: Agent Skills & MyManus

This workspace contains two main components:
1.  **MyManus**: A Python-based autonomous coding agent powered by LLMs and E2B sandboxes.
2.  **Agent Skills System**: A collection of specialized skills (markdown instructions and scripts) defined in `.gemini/skills` and `.claude/skills`.

## 1. MyManus (Python Coding Agent)

Located in the `mymanus/` directory.

### Overview
MyManus is a "code-first" agent that solves problems by writing and executing Python code in a secure E2B Firecracker MicroVM. It supports LLMs compatible with the OpenAI format (e.g., DeepSeek, Qwen) and features both a Web Console and a CLI.

### Technology Stack
*   **Language:** Python 3.12+
*   **Package Manager:** `uv`
*   **Core Deps:** `fastapi`, `e2b-code-interpreter`, `openai` (client), `rich`.
*   **Infrastructure:** E2B Sandboxes (Firecracker MicroVMs).

### Setup & Configuration
1.  **Dependency Management:**
    The project uses `uv` for fast package management.
    ```bash
    cd mymanus
    uv sync
    ```
2.  **Environment:**
    Configure credentials in `mymanus/.env` (copy from `.env.example`).
    *   `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` (for LLM)
    *   `E2B_API_KEY` (for sandbox)

### Running the Application

**Web Console (Recommended):**
Starts a FastAPI server with a web UI for visualizing the agent's workflow and artifacts (charts, HTML).
```bash
cd mymanus
uv run server.py
# Access at http://localhost:8000
```

**CLI Mode:**
Runs the agent in the terminal.
```bash
cd mymanus
uv run main.py
```

### Key Files
*   `mymanus/agent.py`: Core `ManusAgent` logic (LLM loop, tool dispatch).
*   `mymanus/sandbox_e2b.py`: E2B Sandbox integration (MCP Server implementation).
*   `mymanus/server.py`: FastAPI backend for the web UI.
*   `mymanus/web/`: Frontend assets (HTML/JS/Tailwind).

---

## 2. Agent Skills System

Located in `.gemini/skills/` and `.claude/skills/`.

### Overview
This system defines "skills"—specialized capabilities and domain knowledge that can be dynamically loaded by an agent.

### Available Skills
Refer to `AGENTS.md` for the authoritative list of active skills. Common skills include:
*   **frontend-design**: Guidelines for high-quality UI/UX generation.
*   **mcp-builder**: Guide for building Model Context Protocol servers.
*   **playwright-skill**: Browser automation using Playwright.
*   **skill-creator**: Meta-skill for creating new skills.
*   **ui-ux-pro-max**: Comprehensive UI/UX design resource.

### Skill Structure
Each skill directory (e.g., `.gemini/skills/skill-name/`) typically contains:
*   `SKILL.md`: The core prompt/instruction for the skill.
*   `scripts/`: Python or Node.js scripts associated with the skill.
*   `reference/`: Documentation or reference material.

### Usage
Skills are intended to be "read" or "activated" by the agent when a user's request matches the skill's domain.
