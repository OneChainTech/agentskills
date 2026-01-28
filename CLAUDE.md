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

Skills are markdown-based instructions located in `.claude/skills/` (for Claude) and `.gemini/skills/` (for Gemini). Each skill is a self-contained package that extends AI agent capabilities with specialized knowledge, workflows, and tools.

### Skills Catalog (9 Total)

#### 1. UI/UX Design & Frontend (2 skills)

**`frontend-design`** - Creative, Distinctive UI/UX Design
- **Purpose**: Create production-grade frontend interfaces that avoid generic "AI slop" aesthetics
- **Approach**: Bold, creative design with emphasis on distinctive visual choices
- **Key Features**: Typography selection, color theory, motion design, spatial composition
- **Use When**: Building web components, pages, dashboards, or any creative UI work
- **Philosophy**: Intentional design with clear aesthetic direction (minimalist or maximalist)

**`ui-ux-pro-max`** - Systematic UI/UX Design Intelligence
- **Purpose**: Database-driven design system with searchable patterns and best practices
- **Resources**: 50 styles, 21 color palettes, 50 font pairings, 20 chart types, 8 tech stacks
- **Approach**: Structured workflow using Python search scripts for design decisions
- **Use When**: Professional UI work requiring systematic design choices, accessibility, and best practices
- **Tech Stacks**: React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind (default)

**Note**: These two skills are complementary, not duplicates. Use `frontend-design` for creative/artistic work and `ui-ux-pro-max` for systematic/professional UI development.

#### 2. Development Tools (2 skills)

**`mcp-builder`** - Model Context Protocol Server Development
- **Purpose**: Guide for creating high-quality MCP servers that enable LLMs to interact with external services
- **Languages**: TypeScript (recommended) and Python (FastMCP)
- **Process**: 4-phase workflow (Research → Implementation → Review → Evaluation)
- **Use When**: Building MCP servers to integrate external APIs or services
- **Key Features**: Tool design, authentication, error handling, pagination, evaluation creation

**`playwright-skill`** - Browser Automation & Testing
- **Purpose**: Complete browser automation with Playwright for testing and validation
- **Features**: Auto-detects dev servers, writes clean test scripts to /tmp
- **Use Cases**: Test pages, fill forms, screenshots, responsive design, login flows, link checking
- **Use When**: Testing websites, automating browser interactions, validating web functionality
- **Default**: Visible browser mode (headless: false) for debugging

#### 3. Workflow & Planning (2 skills)

**`planning-with-files`** - Manus-Style Planning System
- **Purpose**: Transform workflow to use persistent markdown files as "working memory on disk"
- **Pattern**: 3-file system (task_plan.md, notes.md, deliverable.md)
- **Use When**: Complex tasks, multi-step projects, research tasks, or when tracking progress
- **Key Rules**: Create plan first, read before decide, update after act, store don't stuff
- **Philosophy**: Attention manipulation through file-based state management

**`skill-creator`** - Meta-Skill for Creating Skills
- **Purpose**: Guide for creating effective skills that extend AI agent capabilities
- **Process**: 6-step workflow (Understand → Plan → Initialize → Edit → Package → Iterate)
- **Use When**: Creating new skills or updating existing skills
- **Key Principles**: Concise is key, progressive disclosure, appropriate degrees of freedom
- **Tools**: init_skill.py (initialization), package_skill.py (validation & packaging)

#### 4. Content Creation & Formats (3 skills)

**`json-canvas`** - JSON Canvas File Manipulation
- **Purpose**: Create and edit JSON Canvas files (.canvas) for infinite canvas applications
- **Format**: Nodes (text, file, link, group) and edges (connections)
- **Use When**: Working with .canvas files, creating visual canvases, mind maps, flowcharts
- **Applications**: Obsidian Canvas and other JSON Canvas-compatible tools
- **Features**: Z-index ordering, colors, labels, backgrounds, positioning

**`obsidian-markdown`** - Obsidian Flavored Markdown
- **Purpose**: Create and edit Obsidian-specific markdown syntax
- **Features**: Wikilinks, embeds, callouts, properties (frontmatter), tags, comments
- **Use When**: Working with .md files in Obsidian or when using Obsidian-specific syntax
- **Syntax**: CommonMark + GitHub Flavored Markdown + LaTeX + Obsidian extensions
- **Special Features**: Block references, search links, Mermaid diagrams, footnotes

**`remotion-best-practices`** - Video Creation in React
- **Purpose**: Best practices for Remotion - programmatic video creation using React
- **Topics**: 30+ rule files covering animations, assets, audio, compositions, captions, etc.
- **Use When**: Working with Remotion code for video generation
- **Key Areas**: Timing/interpolation, sequencing, transitions, text animations, 3D content
- **Tools**: Mediabunny integration, Tailwind support, Lottie animations, caption transcription

### Skill Structure

Each skill follows a consistent structure:
- **`SKILL.md`**: Core instructions with YAML frontmatter (name, description)
- **`scripts/`**: Executable code (Python/Node.js) for deterministic operations
- **`reference/`**: Documentation loaded as needed to keep SKILL.md lean
- **`assets/`**: Files used in output (templates, icons, fonts, etc.)

### Skills Usage Guidelines

- Skills are loaded dynamically when user requests match the skill's domain
- Each skill provides specialized knowledge and workflows not available in base models
- Skills use progressive disclosure: metadata → SKILL.md → bundled resources
- No duplicate skills detected - all 9 skills serve distinct purposes

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
