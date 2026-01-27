# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This workspace contains two main Python applications and a collection of AI agent skills:

1. **MyManus** (`mymanus/`): An autonomous coding agent powered by LangGraph and E2B sandboxes
2. **RAG Application** (`rag/`): A hybrid search RAG system with web UI
3. **Agent Skills** (`.claude/skills/` and `.gemini/skills/`): Reusable skill definitions for AI agents

## Development Environment

- **Python Version**: 3.12+ (MyManus), 3.11+ (RAG)
- **Package Manager**: `uv` (fast Python package manager)
- **Dependency Management**: Each project has its own `pyproject.toml`

## Common Commands

### MyManus (Autonomous Coding Agent)

```bash
# Navigate to project
cd mymanus

# Install dependencies
uv sync

# Run web console (recommended)
uv run server.py
# Access at http://localhost:8000

# Run CLI mode
uv run main.py
```

**Environment Variables** (create `.env` from `.env.example`):
- `DEEPSEEK_API_KEY`: LLM API key
- `DEEPSEEK_BASE_URL`: LLM API endpoint
- `E2B_API_KEY`: E2B sandbox API key

### RAG Application

```bash
# Navigate to project
cd rag

# Install dependencies
uv sync

# Run server
uv run server.py
# Access at http://localhost:8000/web/index.html
```

**Environment Variables**:
- `DEEPSEEK_API_KEY`: API key for SiliconFlow
- `DEEPSEEK_BASE_URL`: https://api.siliconflow.cn/v1
- `MODEL_ID`: Qwen/Qwen3-Coder-30B-A3B-Instruct

## Architecture

### MyManus Architecture

**Three-Layer Design**:

1. **Frontend Layer** (`mymanus/web/`): HTML5/Tailwind web console with SSE streaming
2. **Orchestration Layer** (`mymanus/agent.py`, `mymanus/server.py`):
   - `agent.py`: LangGraph state machine with ReAct loop and memory
   - `server.py`: FastAPI backend with SSE endpoints
3. **Execution Layer** (`mymanus/sandbox_e2b.py`): E2B Code Interpreter integration via MCP

**Key Components**:
- **Agent Core**: Uses LangGraph's `create_agent` with MemorySaver for stateful conversations
- **Tools**: Code execution, shell commands, file operations, visualization, and web service hosting
- **Sandbox**: Isolated Firecracker MicroVMs via E2B Cloud

### RAG Architecture

**Three-Layer Design**:

1. **Frontend**: Single-page app for file uploads and chat
2. **API Layer** (`rag/server.py`): FastAPI with `/upload` and `/chat` endpoints
3. **RAG Engine** (`rag/rag_engine.py`):
   - **Ingestion**: BAAI/bge-m3 embeddings → FAISS + BM25 indexing
   - **Retrieval**: EnsembleRetriever (hybrid vector + keyword search)
   - **Reranking**: Custom SiliconFlowReranker with BAAI/bge-reranker-v2-m3
   - **Generation**: Qwen-Coder-30B via SiliconFlow API

## Agent Skills System

Skills are markdown-based instructions located in `.claude/skills/` (for Claude) and `.gemini/skills/` (for Gemini).

**Available Skills**:
- `frontend-design`: High-quality UI/UX generation guidelines
- `mcp-builder`: Guide for building Model Context Protocol servers
- `playwright-skill`: Browser automation with Playwright
- `skill-creator`: Meta-skill for creating new skills
- `ui-ux-pro-max`: Comprehensive UI/UX design resource with 50 styles, 21 palettes, 50 font pairings
- `planning-with-files`: Manus-style persistent markdown planning
- `remotion-best-practices`: Video creation in React with Remotion
- `json-canvas`: JSON Canvas file manipulation
- `obsidian-markdown`: Obsidian Flavored Markdown support

**Skill Structure**:
- `SKILL.md`: Core prompt/instruction
- `scripts/`: Associated Python/Node.js scripts
- `reference/`: Documentation and examples

## Important Notes

### MyManus Specifics

- **System Prompt**: Located in `agent.py`, defines agent behavior including UI/UX standards (Bento Grid, Glassmorphism, no emojis in formal UI)
- **Web Services**: When starting Gradio/Streamlit, must kill existing processes on port first
- **Gradio Version**: Use 3.50.2 (not 4.x) to avoid reverse proxy issues
- **File Encoding**: Always use `encoding='utf-8'` for Chinese text
- **Visualization**: Must call `visualize_file` or `get_public_url` tools to trigger frontend preview

### RAG Specifics

- **Hybrid Search**: Combines semantic (FAISS) and keyword (BM25) retrieval
- **Reranking**: Cross-encoder reranking improves relevance
- **File Support**: `.txt`, `.md`, `.csv` files
- **Verification**: Use `verify_rag.py` for standalone testing

### Skills Usage

Skills are intended to be loaded dynamically by AI agents when user requests match the skill's domain. Each skill provides specialized knowledge and workflows.
