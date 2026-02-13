# OCR 文档解析与问答系统

一个基于 FastAPI 的 OCR + RAG 服务：
- 支持 PDF/图片上传并解析为 Markdown。
- 保留页面坐标信息，支持前端框选高亮。
- 使用向量检索 + BM25 混合召回，并可选重排。
- 提供历史记录、上传进度 SSE、对话问答接口。

## 核心能力

- 文档解析
  - `utils/pdf_handler.py`：PDF 渲染为逐页图片。
  - `engine/ocr.py`：调用多模态模型提取 `grounded_markdown` 与坐标框。
- 检索与问答
  - `retrieval.py`：分块、混合检索、RRF 融合、可选 rerank、答案生成。
  - 向量库使用 Chroma `EphemeralClient`（内存模式）。
- 服务接口
  - `server.py`：上传、历史记录、SSE 进度、问答 API。
- 前端
  - `web/index.html`：上传、历史回放、Markdown/可视化、对话交互。

## 目录结构

```text
ocr/
├── engine/ocr.py
├── utils/pdf_handler.py
├── retrieval.py
├── server.py
├── web/index.html
├── architecture.canvas
├── pyproject.toml
├── data/              # 运行时数据（已在 .gitignore 中忽略）
└── ocrdata/           # 示例文件（手工测试用）
```

## 运行要求

- Python 3.12+
- `uv`（推荐）

## 快速开始

1. 安装依赖

```bash
cd ocr
uv sync
```

2. 配置环境变量（`ocr/.env`）

```ini
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
OCR_MODEL_ID=deepseek-ai/DeepSeek-OCR
BASE_MODEL_ID=Pro/zai-org/GLM-4.7
EMBEDDING_MODEL_ID=BAAI/bge-m3
```

3. 启动服务

```bash
uv run server.py
```

浏览器访问：`http://localhost:8000`

## API 概览

- `POST /upload`：上传文档并触发 OCR + 建索引。
- `GET /upload_status/{upload_id}`：查询上传状态。
- `GET /upload_events/{upload_id}`：SSE 进度事件流。
- `POST /query`：基于当前索引进行多轮问答。
- `GET /history`：历史记录列表。
- `POST /history/load`：加载历史记录并重建索引。
- `DELETE /history/{upload_id}`：删除历史记录与对应图片。

## 本次整理

- 删除未使用导入：`ocr/utils/pdf_handler.py`
- 删除未使用变量：`ocr/retrieval.py`
- 修复可变默认值：`ocr/server.py` 中 `QueryRequest.history`
- 文档与架构图更新为与现有实现一致
