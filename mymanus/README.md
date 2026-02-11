# MyManus

MyManus 是一个面向工程实践的自主编程智能体，基于 DeepAgents + LangGraph 的多轮推理框架，提供 Web/CLI 双入口，并支持 E2B 与 OpenSandbox 两种沙箱执行环境。

核心定位：让智能体“能写、能跑、能展示”，并通过可控的工具调用与可视化预览完成闭环交付。

## 主要特性

- 多智能体协作：主智能体负责规划与调度，CodeWriter/CodeReviewer 负责写码与审查。
- 深度推理与记忆：LangGraph 状态机 + MemorySaver，支持多轮上下文与恢复执行。
- 多沙箱适配：统一 BaseSandbox 接口，E2B 与 OpenSandbox 可切换。
- Web 实时界面：流式 NDJSON 输出、文件预览、HITL 审批卡片、沙箱选择。
- CLI 交互模式：Rich 终端体验，适合快速验证与调试。
- 技能系统：任务文本中包含技能名时自动注入技能指引（见 `skills/`）。

## 架构概览

- 交互层：`web/index.html`（Web Console）与 `main.py`（CLI）。
- 服务层：`server.py`（FastAPI），提供 `/api/run`、`/api/upload`、`/api/skills`。
- 智能体层：`agent.py`（DeepAgents + LangGraph），内置 HITL 中间件。
- 工具层：`tools.py` 封装 run_code/run_shell_command/visualize_file 等能力。
- 沙箱层：`sandbox_interface.py` + `sandbox_adapter_e2b.py` + `sandbox_adapter_opensandbox.py`。

HITL 说明：当前默认仅对 `visualize_file` 进行审批拦截，前端会展示 Security Check 卡片。

## 项目结构

```text
mymanus/
├── agent.py                      # 智能体核心（DeepAgents/LangGraph/Subagents）
├── tools.py                      # 工具封装（run_code/run_shell_command/visualize_file 等）
├── sandbox_interface.py          # 沙箱抽象接口（BaseSandbox）
├── sandbox_adapter_e2b.py        # E2B 适配器
├── sandbox_adapter_opensandbox.py # OpenSandbox 适配器
├── server.py                     # FastAPI 服务（/api/run /api/upload /api/skills）
├── main.py                       # CLI 入口（Rich）
├── web/                          # 前端资源（Web Console）
├── skills/                       # 技能指引（SKILL.md）
├── uploads/                      # 上传文件目录
├── downloads/                    # 下载产物目录
├── architecture.canvas           # 项目架构图（Obsidian Canvas）
├── .env.example                  # 环境变量示例
└── start-opensandbox.sh          # OpenSandbox 启动脚本
```

## 快速开始

### 1. 环境准备

- Python 3.12+
- `uv` 包管理器
- 如果使用 OpenSandbox，请确保 `../OpenSandbox` 已存在并可用

```bash
cd mymanus
cp .env.example .env
```

### 2. 配置环境变量

在 `.env` 中至少配置以下项：

- `DEEPSEEK_API_KEY`：LLM API Key
- `DEEPSEEK_BASE_URL`：可选，默认在 `.env.example` 中给出
- `MODEL_ID`：可选，默认 `deepseek-ai/DeepSeek-V3`

如果使用 E2B：
- `E2B_API_KEY`

如果使用 OpenSandbox：
- `OPEN_SANDBOX_DOMAIN`（默认 `127.0.0.1:8082`）
- `OPEN_SANDBOX_API_KEY`（本地可留空）

### 3. 安装依赖

```bash
uv sync
```

### 4. 启动 OpenSandbox（可选）

```bash
./start-opensandbox.sh
```

### 5. 启动服务

Web 模式：
```bash
uv run server.py
```
访问：http://localhost:8000

CLI 模式：
```bash
uv run main.py
```

## 运行流程（简述）

1. Web/CLI 将任务发送给 `ManusAgent`。
2. 智能体调用工具（`tools.py`），工具统一访问沙箱接口。
3. 沙箱适配器连接 E2B 或 OpenSandbox 执行代码/命令。
4. 执行结果以 NDJSON 流回前端并可视化展示。

## 架构图

- 文件：`architecture.canvas`
- 可用 Obsidian 或支持 Canvas 的工具打开查看。
