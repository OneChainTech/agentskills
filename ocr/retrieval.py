import os
import re
import time
import httpx
import chromadb
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import Document

load_dotenv()

# 优化：预编译正则表达式以提升性能
TAG_PATTERN = re.compile(
    r"(<\|ref\|>.*?<\|/ref\|>\s*<\|det\|>.*?<\|/det\|>)",
    re.DOTALL
)
GROUNDING_PATTERN = re.compile(
    r"<\|det\|>\s*\[\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\]\s*<\|/det\|>",
    re.DOTALL
)
CLEAN_PATTERN = re.compile(
    r"<\|ref\|>|<\|/ref\|>|<\|det\|>\[\[.*?\]\]<\|/det\|>",
    re.DOTALL
)

class SiliconFlowReranker:
    """
    Simple wrapper for SiliconFlow/BAAI Rerank API
    """
    def __init__(self, top_k=3):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.siliconflow.cn/v1/rerank"
        self.model = "BAAI/bge-reranker-v2-m3"
        self.top_k = top_k

    def rerank(self, query: str, documents: list[Document]) -> list[Document]:
        if not documents:
            return []
            
        doc_texts = [doc.page_content for doc in documents]
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": doc_texts,
            "top_n": self.top_k,
            "return_documents": False
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=20.0
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                
                # Re-order documents based on rerank scores
                reranked_docs = []
                for res in results:
                    idx = res["index"]
                    if idx >= len(documents): continue
                    doc = documents[idx]
                    # Add score to metadata for debugging
                    doc.metadata["relevance_score"] = float(res.get("relevance_score", 0.0))
                    reranked_docs.append(doc)
                
                if reranked_docs:
                    print(f"[+] Reranked: Top score {reranked_docs[0].metadata['relevance_score']}")
                return reranked_docs
        except Exception as e:
            print(f"[-] Rerank API Failed: {e}, falling back to original order.")
            return documents[:self.top_k]

class PDFRetriever:
    def __init__(self):
        # 核心修改：使用内存模式 (EphemeralClient)，彻底解决磁盘只读错误，提升检索响应速度
        # 禁用匿名遥测，防止因无法连接 PostHog 导致的上传失败
        from chromadb.config import Settings
        self.client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
        
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            model=os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-m3"),
            chunk_size=100,  # 优化：批量处理 embedding 请求
            max_retries=2    # 优化：减少重试次数以加速失败场景
        )
        
        self.llm = ChatOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            model=os.getenv("BASE_MODEL_ID", "Pro/zai-org/GLM-4.7"),
            temperature=0,
            request_timeout=120  # 增加到 120 秒
        )
        self.ensemble_retriever = None
        self.reranker = SiliconFlowReranker(top_k=3)
        self.enable_query_rewrite = os.getenv("ENABLE_QUERY_REWRITE", "1") == "1"  # 默认开启，提升多轮对话准确度
        self.enable_multi_query = os.getenv("ENABLE_MULTI_QUERY", "0") == "1"  # 保持关闭，加速
        self.multi_query_count = int(os.getenv("MULTI_QUERY_COUNT", "2"))
        self.enable_rerank = os.getenv("ENABLE_RERANK", "1") == "1"  # 默认开启 rerank，提升准确度
        self.rerank_threshold = int(os.getenv("RERANK_THRESHOLD", "2"))
        self.vector_k = int(os.getenv("VECTOR_K", "10"))
        self.bm25_k = int(os.getenv("BM25_K", "10"))
        self.initial_candidate_limit = int(os.getenv("INITIAL_CANDIDATE_LIMIT", "20"))
        self.final_context_docs = int(os.getenv("FINAL_CONTEXT_DOCS", "5"))
        self.answer_timeout_sec = int(os.getenv("ANSWER_TIMEOUT_SEC", "120"))  # 增加到 120 秒
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
        self.min_chunk_chars = int(os.getenv("MIN_CHUNK_CHARS", "40")) # 降低门槛，保留精简但关键的信息
        self.max_chunks_per_page = int(os.getenv("MAX_CHUNKS_PER_PAGE", "10"))
        self.max_total_chunks = int(os.getenv("MAX_TOTAL_CHUNKS", "80"))
        self.current_upload_id = None

    def _invoke_with_timeout(self, runnable, payload: dict, timeout_sec: int):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(runnable.invoke, payload)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            future.cancel()
            raise TimeoutError(f"invoke timeout after {timeout_sec}s")
        finally:
            # Don't block caller waiting for timed-out worker thread.
            executor.shutdown(wait=False, cancel_futures=True)

    def _normalize_box(self, box: dict) -> dict:
        try:
            x = float(box.get("x", 0))
            y = float(box.get("y", 0))
            w = float(box.get("w", 100))
            h = float(box.get("h", 100))
            x = max(0.0, min(100.0, x))
            y = max(0.0, min(100.0, y))
            w = max(0.0, min(100.0 - x, w))
            h = max(0.0, min(100.0 - y, h))
            return {
                "type": str(box.get("type", "文本")),
                "x": round(x, 2),
                "y": round(y, 2),
                "w": round(w, 2),
                "h": round(h, 2),
            }
        except Exception:
            return {"type": "文本", "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0}

    def _is_table_block(self, block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            return False
        has_pipe = sum(1 for ln in lines if "|" in ln) >= 2
        has_sep = any("---" in ln and "|" in ln for ln in lines)
        return has_pipe and has_sep

    def _split_by_grounding_boundaries(self, text: str, chunk_size: int) -> list[str]:
        """
        按 grounding 标签对的边界切分文本，确保不在 <|ref|>...<|/ref|><|det|>...<|/det|> 内部断开。
        将文本拆分为独立的标签对片段，然后按 chunk_size 合并相邻片段。
        优化：使用预编译的正则表达式
        """
        # 将文本分割为 [标签对, 间隙文本, 标签对, ...] 的序列
        parts = TAG_PATTERN.split(text)
        # parts 是交替的 [间隙, 标签对, 间隙, 标签对, ...] 序列
        parts = [p for p in parts if p.strip()]

        if not parts:
            return [text] if text.strip() else []

        chunks = []
        buf = ""
        for part in parts:
            candidate = f"{buf}\n\n{part}".strip() if buf else part
            if len(candidate) <= chunk_size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                # 单个 part 超过 chunk_size 也保留完整（不在标签内切断）
                buf = part
        if buf:
            chunks.append(buf)

        return chunks if chunks else [text]

    def _split_long_text_with_overlap(self, text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        # 如果文本包含 grounding 标签，使用标签边界切分，防止截断标签对
        if "<|ref|>" in text and "<|det|>" in text:
            return self._split_by_grounding_boundaries(text, chunk_size)

        chunks = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + chunk_size, n)
            if end < n:
                pivot = max(
                    text.rfind("。", start, end),
                    text.rfind("！", start, end),
                    text.rfind("？", start, end),
                    text.rfind("\n", start, end),
                )
                if pivot > start + int(chunk_size * 0.6):
                    end = pivot + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= n:
                break
            start = max(end - chunk_overlap, start + 1)
        return chunks

    def _split_markdown_chunks(
        self,
        markdown: str,
        chunk_size: int,
        chunk_overlap: int,
        min_chunk_chars: int
    ) -> list[str]:
        text = (markdown or "").strip()
        if not text:
            return []

        # 核心优化：识别带坐标标签的原子块，避免坐标标签与正文分离
        # 优化：使用预编译的正则表达式
        if "<|ref|>" in text and "<|det|>" in text:
            # 匹配模式：<|ref|>...<|/ref|><|det|>...<|/det|> 或者 模型可能输出的变体
            # 这里使用贪婪匹配逻辑来切割独立的逻辑块
            blocks = TAG_PATTERN.findall(text)
            if not blocks:
                # 如果没找到标准 ref/det，尝试按换行符初步切分
                blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        else:
            blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
            
        if not blocks:
            blocks = [text]

        chunks = []
        buf = ""
        for block in blocks:
            # 检查是否是表格（ grounded markdown 中表格也会被包含在 ref 中）
            is_table = self._is_table_block(block)
            
            if is_table:
                if buf:
                    chunks.extend(self._split_long_text_with_overlap(buf, chunk_size, chunk_overlap))
                    buf = ""
                chunks.append(block)
                continue

            candidate = f"{buf}\n\n{block}".strip() if buf else block
            if len(candidate) <= chunk_size:
                buf = candidate
            else:
                if buf:
                    chunks.extend(self._split_long_text_with_overlap(buf, chunk_size, chunk_overlap))
                
                # 如果单个 block 就超过了 chunk_size，则强制切分
                if len(block) > chunk_size:
                    chunks.extend(self._split_long_text_with_overlap(block, chunk_size, chunk_overlap))
                    buf = ""
                else:
                    buf = block

        if buf:
            chunks.extend(self._split_long_text_with_overlap(buf, chunk_size, chunk_overlap))

        deduped = []
        seen = set()
        for chunk in chunks:
            # 清理后检查长度 - 优化：使用预编译的正则表达式
            clean = CLEAN_PATTERN.sub("", chunk).strip()
            normalized = " ".join(clean.split())
            if len(normalized) < min_chunk_chars:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(chunk)
        return deduped

    def _infer_chunk_type(self, chunk: str) -> str:
        # 先清洗掉 grounded 标签再判断类型，增加准确性
        # 优化：使用预编译的正则表达式
        text = CLEAN_PATTERN.sub("", chunk).strip()
        lowered = text.lower()
        if self._is_table_block(text):
            return "表格"
        # 优化：避免误判普通文本中包含“图”字的情况
        chart_keywords = ["figure", "diagram", "chart", "流程图", "架构图", "拓扑图", "示意图", "统计图", "时序图"]
        if any(k in lowered for k in chart_keywords):
            return "图表"
        # 更加严格的匹配：如果包含“图”字，且位于段落开头并紧跟数字（如 图1.）
        if re.search(r"^(图|fig|figure)\s*\d+", lowered):
            return "图表"
        return "文本"

    def ingest_pages(self, page_data: list, chunk_config: dict | None = None):
        """
        全量 Markdown 页面索引
        """
        try:
            ingest_start = time.perf_counter()
            print(f"[*] Ingesting {len(page_data)} pages into memory...")
            chunk_size = int((chunk_config or {}).get("chunk_size", self.chunk_size))
            chunk_overlap = int((chunk_config or {}).get("chunk_overlap", self.chunk_overlap))
            min_chunk_chars = int((chunk_config or {}).get("min_chunk_chars", self.min_chunk_chars))
            max_chunks_per_page = int((chunk_config or {}).get("max_chunks_per_page", self.max_chunks_per_page))
            max_total_chunks = int((chunk_config or {}).get("max_total_chunks", self.max_total_chunks))

            chunk_size = max(200, min(3000, chunk_size))
            chunk_overlap = max(0, min(chunk_size - 1, chunk_overlap))
            min_chunk_chars = max(20, min(300, min_chunk_chars))
            max_chunks_per_page = max(1, min(100, max_chunks_per_page))
            max_total_chunks = max(10, min(1000, max_total_chunks))

            documents = []
            chunk_uid = 0
            chunks_before_limit = 0
            chunks_after_limit = 0
            chunk_build_start = time.perf_counter()
            for p in page_data:
                page_num = p.get("page", 1)
                # 优先使用带标签的文本进行切分，以保证坐标匹配
                markdown = p.get("grounded_markdown", p.get("markdown", ""))
                page_boxes = [self._normalize_box(b) for b in (p.get("boxes") or [])]
                
                chunks = self._split_markdown_chunks(
                    markdown,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    min_chunk_chars=min_chunk_chars,
                )
                chunks_before_limit += len(chunks)
                if len(chunks) > max_chunks_per_page:
                    chunks = chunks[:max_chunks_per_page]
                chunks_after_limit += len(chunks)

                if not chunks:
                    continue

                for idx, chunk in enumerate(chunks):
                    # 1. 提取 chunk 中所有交织的坐标标签，计算联合 bbox
                    # 优化：使用预编译的正则表达式
                    all_groundings = GROUNDING_PATTERN.findall(chunk)

                    bbox = None
                    if all_groundings:
                        try:
                            coords = [(int(m[0]), int(m[1]), int(m[2]), int(m[3])) for m in all_groundings]
                            min_x1 = min(c[0] for c in coords)
                            min_y1 = min(c[1] for c in coords)
                            max_x2 = max(c[2] for c in coords)
                            max_y2 = max(c[3] for c in coords)
                            inferred_type = self._infer_chunk_type(chunk)
                            bbox = {
                                "x": min_x1 / 10, "y": min_y1 / 10,
                                "w": (max_x2 - min_x1) / 10, "h": (max_y2 - min_y1) / 10,
                                "type": inferred_type
                            }
                        except Exception:
                            bbox = None

                    # 无论是否找到 bbox，都必须清洗 chunk，移除所有 grounding 标签
                    # 优化：使用预编译的正则表达式
                    clean_chunk = CLEAN_PATTERN.sub("", chunk).strip()

                    if not bbox:
                        # 2. 增强型文本匹配：通过文本相似度在原始 Box 中寻找最接近的坐标
                        clean_text_for_match = re.sub(r"\s+", "", clean_chunk)
                        sample_long = clean_text_for_match[:80]

                        best_match_box = None
                        best_ratio = 0.0

                        for original_box in page_boxes:
                            original_text = re.sub(r"\s+", "", original_box.get("text", ""))
                            if not original_text:
                                continue

                            # 方案 A: 包含匹配（用更长的样本提高准确性）
                            if sample_long and sample_long in original_text:
                                best_match_box = original_box
                                best_ratio = 1.0
                                break

                            # 方案 B: SequenceMatcher 模糊匹配（替代不可靠的字符集重合）
                            ratio = SequenceMatcher(
                                None,
                                clean_text_for_match[:100],
                                original_text[:200]
                            ).ratio()
                            if ratio > best_ratio:
                                best_ratio = ratio
                                best_match_box = original_box

                        # 只有相似度足够高才认定为有效匹配
                        if best_match_box and best_ratio > 0.4:
                            bbox = best_match_box
                        else:
                            # 最终降级：返回整页范围，不再使用不可靠的索引匹配
                            bbox = {"type": "文本", "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0}

                    metadata = {
                        "page": page_num,
                        "chunk_id": f"p{page_num}_c{chunk_uid}",
                        "chunk_index": idx,
                        "box_type": bbox.get("type", "文本"),
                        "bbox_x": bbox["x"],
                        "bbox_y": bbox["y"],
                        "bbox_w": bbox["w"],
                        "bbox_h": bbox["h"],
                    }
                    documents.append(Document(page_content=clean_chunk, metadata=metadata))
                    chunk_uid += 1

            if len(documents) > max_total_chunks:
                documents = documents[:max_total_chunks]
                print(f"[!] Chunk count limited to {max_total_chunks} for faster ingestion.")
            chunk_build_ms = round((time.perf_counter() - chunk_build_start) * 1000, 2)

            if not documents:
                total_ms = round((time.perf_counter() - ingest_start) * 1000, 2)
                return {
                    "doc_count": 0,
                    "pages": len(page_data),
                    "chunk_config": {
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "min_chunk_chars": min_chunk_chars,
                        "max_chunks_per_page": max_chunks_per_page,
                        "max_total_chunks": max_total_chunks,
                    },
                    "chunks_before_limit": chunks_before_limit,
                    "chunks_after_limit": chunks_after_limit,
                    "chunk_build_ms": chunk_build_ms,
                    "index_ms": 0.0,
                    "total_ms": total_ms,
                }

            # 内存中创建临时向量库
            index_start = time.perf_counter()
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                client=self.client,
                collection_name=f"temp_idx_{int(time.time())}"
            )
            
            # 初始化 BM25
            bm25_retriever = BM25Retriever.from_documents(documents)
            bm25_retriever.k = self.bm25_k

            # 构造混合检索器
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[vectorstore.as_retriever(search_kwargs={"k": self.vector_k}), bm25_retriever],
                weights=[0.6, 0.4]
            )
            index_ms = round((time.perf_counter() - index_start) * 1000, 2)
            total_ms = round((time.perf_counter() - ingest_start) * 1000, 2)
            
            print("[+] Hybrid index established in memory.")
            print(
                f"[+] Ingest stats: docs={len(documents)}, chunks_before={chunks_before_limit}, "
                f"chunks_after={chunks_after_limit}, build={chunk_build_ms}ms, index={index_ms}ms, total={total_ms}ms"
            )
            return {
                "doc_count": len(documents),
                "pages": len(page_data),
                "chunk_config": {
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "min_chunk_chars": min_chunk_chars,
                    "max_chunks_per_page": max_chunks_per_page,
                    "max_total_chunks": max_total_chunks,
                },
                "chunks_before_limit": chunks_before_limit,
                "chunks_after_limit": chunks_after_limit,
                "chunk_build_ms": chunk_build_ms,
                "index_ms": index_ms,
                "total_ms": total_ms,
            }
        except Exception as e:
            print(f"[-] Ingest Error: {e}")
            raise e

    def generate_multi_queries(self, question: str):
        """
        RAG-Fusion: Generate multiple query variations
        """
        prompt = PromptTemplate(
            input_variables=["question"],
            template="""你是一个智能助手。请针对以下问题生成 4 个不同角度的搜索查询，用于在文档中检索相关信息。
请直接输出 4 行查询，每行一个，不要包含序号或额外解释。
原问题：{question}"""
        )
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            print(f"[*] Generating multi-view queries for RAG-Fusion...")
            res = chain.invoke({"question": question})
            queries = [q.strip() for q in res.split('\n') if q.strip()]
            return queries[:self.multi_query_count]
        except Exception as e:
            print(f"[-] Multi-query generation failed: {e}")
            return []

    def reciprocal_rank_fusion(self, results: list[list[Document]], k=60):
        """
        RAG-Fusion: RRF Algorithm
        """
        fused_scores = {}
        doc_map = {}
        
        for docs in results:
            for rank, doc in enumerate(docs):
                doc_key = doc.metadata.get("chunk_id") or f'{doc.metadata.get("page", 0)}::{doc.page_content[:80]}'
                if doc_key not in doc_map:
                    doc_map[doc_key] = doc

                if doc_key not in fused_scores:
                    fused_scores[doc_key] = 0

                fused_scores[doc_key] += 1 / (rank + k)

        reranked_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        for key, score in reranked_results:
            doc_map[key].metadata["relevance_score"] = score
        return [doc_map[key] for key, score in reranked_results]

    def query(self, question: str, history: list[dict] = []):
        if not self.ensemble_retriever:
            return {"answer": "系统尚未加载文档，请先上传。", "sources": []}
        query_start = time.perf_counter()

        # 0. Format History
        chat_history_str = ""
        for msg in history[-6:]:  # Keep last 6 messages context
            role = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '').replace('\n', ' ')
            chat_history_str += f"{role}: {content}\n"

        # 1. Standalone Question Generation (Query Rewriting)
        search_query = question
        if self.enable_query_rewrite and chat_history_str.strip():
            condense_template = """结合以下对话历史，将用户的后续问题改写为一个完整的、独立的搜索查询，以便于在文档中进行检索。
保持中文，不要回答问题，仅仅是改写问题使其包含上下文信息。

对话历史：
{chat_history}

后续问题：{question}

独立查询："""
            condense_prompt = PromptTemplate.from_template(condense_template)
            condense_chain = condense_prompt | self.llm | StrOutputParser()
            
            try:
                print(f"[*] Rewriting query for context...")
                res = condense_chain.invoke({"chat_history": chat_history_str, "question": question})
                search_query = res.strip()
                print(f"[+] Standalone Query: {search_query}")
            except Exception as e:
                print(f"[-] Query Rewrite Error: {e}, using original question.")

        # 2. RAG-Fusion: Multi-Query Retrieval + RRF
        try:
            # 2.1 Generate queries
            generated_queries = self.generate_multi_queries(search_query) if self.enable_multi_query else []
            all_queries = [search_query] + generated_queries
            print(f"[+] RAG-Fusion Queries: {all_queries}")

            # 2.2 Parallel Retrieval
            all_results = []
            for q in all_queries:
                try:
                    docs = self.ensemble_retriever.invoke(q)
                    all_results.append(docs)
                except Exception as inner_e:
                    print(f"[-] Retrieve failed on query '{q}': {inner_e}")
            
            # 2.3 RRF Fusion
            initial_docs = self.reciprocal_rank_fusion(all_results)
            print(f"[+] RRF Fused {len(initial_docs)} documents from {len(all_queries)} queries.")
            
            # Keep top candidates for reranking / answering
            initial_docs = initial_docs[:self.initial_candidate_limit]

        except Exception as e:
            print(f"[-] Retrieval Error: {e}")
            return {"answer": f"检索出错: {str(e)}", "sources": []}

        if not initial_docs:
            return {"answer": "未检索到相关内容，请尝试更具体的问题或重新上传更清晰的文档。", "sources": []}

        # 3. Second Pass: Reranking (Refine to top 3)
        rerank_start = time.perf_counter()
        if self.enable_rerank and len(initial_docs) >= self.rerank_threshold:
            final_docs = self.reranker.rerank(search_query, initial_docs)
        else:
            final_docs = initial_docs[:self.final_context_docs]
        rerank_ms = round((time.perf_counter() - rerank_start) * 1000, 2)
        print(f"[+] Rerank stage done in {rerank_ms}ms, docs={len(final_docs)}")

        if not final_docs:
            final_docs = initial_docs[:self.final_context_docs]

        prompt_template = """你是一个高精度的图文分析专家。
当前背景：你面前是一份经过 OCR 精准转录的【原始 Markdown 源码】。
这些源码完整保留了文档中的所有文字、表格数据、图表标签和流程逻辑。

操作规范：
1. 基于上下文源码回答用户问题。
2. 如果用户询问数据，请直接从 Markdown 表格或列表中定位原始数值。
3. 严禁对事实进行任何润色、翻译或总结，保持原文的专业术语。
4. 如果信息分布在多个页面，请结合各页面源码给出完整结论。

上下文源码：
{context}

对话历史：
{chat_history}

用户问题：{question}
请以中文回答（严格基于源码，保留数据准确性）："""

        PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "chat_history", "question"])
        answer_chain = PROMPT | self.llm | StrOutputParser()

        try:
            context_text = "\n\n".join([doc.page_content for doc in final_docs])
            payload = {
                "context": context_text,
                "question": question,
                "chat_history": chat_history_str
            }
            print(f"[*] Generating answer with {len(final_docs)} docs, context_len={len(context_text)}...")
            answer_start = time.perf_counter()
            answer_text = self._invoke_with_timeout(answer_chain, payload, self.answer_timeout_sec)
            answer_ms = round((time.perf_counter() - answer_start) * 1000, 2)
            print(f"[+] Answer generation done in {answer_ms}ms")
            
            # Format sources with page numbers, image URLs and bbox grounding
            sources = []
            seen_chunk_ids = set()
            for doc in final_docs:
                page_num = doc.metadata.get("page", 1)
                score = doc.metadata.get('relevance_score', 0.0)
                if not isinstance(score, (int, float)):
                    score = 0.0
                
                preview = doc.page_content[:100].replace('\n', ' ') + "..."
                chunk_id = doc.metadata.get("chunk_id")
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)

                # Generate image URL with timestamp to prevent caching
                ts = int(time.time())
                upload_prefix = f"/{self.current_upload_id}" if self.current_upload_id else ""
                image_url = f"/images{upload_prefix}/page_{page_num}.png?t={ts}"
                bbox = {
                    "x": float(doc.metadata.get("bbox_x", 0.0)),
                    "y": float(doc.metadata.get("bbox_y", 0.0)),
                    "w": float(doc.metadata.get("bbox_w", 100.0)),
                    "h": float(doc.metadata.get("bbox_h", 100.0)),
                }
                box_type = doc.metadata.get("box_type", "Text")

                sources.append({
                    "page": page_num,
                    "preview": preview,
                    "score": float(score),
                    "image_url": image_url,
                    "bbox": bbox,
                    "box_type": box_type
                })

            # Sort sources by score descending to fulfill user request
            sources.sort(key=lambda x: x['score'], reverse=True)

            return {
                "answer": answer_text,
                "sources": sources
            }
        except Exception as e:
            print(f"[-] Query Generation Error: {e}")
            fallback = []
            fallback_sources = []
            seen_pages = set()
            for i, d in enumerate(final_docs[:3]):
                page_num = d.metadata.get("page", 1)
                snippet = d.page_content[:180].replace('\n', ' ')
                fallback.append(f"[P{page_num}] {snippet}")
                if page_num in seen_pages:
                    continue
                seen_pages.add(page_num)
                ts = int(time.time())
                upload_prefix = f"/{self.current_upload_id}" if self.current_upload_id else ""
                fallback_sources.append({
                    "page": page_num,
                    "preview": snippet,
                    "score": 1.0 / (i + 1), # Dummy score for fallback
                    "image_url": f"/images{upload_prefix}/page_{page_num}.png?t={ts}",
                    "bbox": {
                        "x": float(d.metadata.get("bbox_x", 0.0)),
                        "y": float(d.metadata.get("bbox_y", 0.0)),
                        "w": float(d.metadata.get("bbox_w", 100.0)),
                        "h": float(d.metadata.get("bbox_h", 100.0)),
                    },
                    "box_type": d.metadata.get("box_type", "Text")
                })
            elapsed_ms = round((time.perf_counter() - query_start) * 1000, 2)
            text = "问答生成超时或失败，以下是最相关片段：\n" + "\n".join(fallback) if fallback else f"生成回答出错: {str(e)}"
            print(f"[-] Query fallback in {elapsed_ms}ms")
            return {"answer": text, "sources": fallback_sources}
