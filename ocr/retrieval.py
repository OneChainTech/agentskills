import os
import time
import httpx
import chromadb
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_core.prompts import PromptTemplate
from langchain.schema import Document

load_dotenv()

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
                    timeout=10.0
                )
                response.raise_for_status()
                results = response.json().get("results", [])
                
                # Re-order documents based on rerank scores
                reranked_docs = []
                for res in results:
                    idx = res["index"]
                    doc = documents[idx]
                    # Add score to metadata for debugging
                    doc.metadata["relevance_score"] = res["relevance_score"]
                    reranked_docs.append(doc)
                
                print(f"[+] Reranked: Top score {results[0]['relevance_score'] if results else 0}")
                return reranked_docs
        except Exception as e:
            print(f"[-] Rerank API Failed: {e}, falling back to original order.")
            return documents[:self.top_k]

class PDFRetriever:
    def __init__(self):
        # 核心修改：使用内存模式 (EphemeralClient)，彻底解决磁盘只读错误，提升检索响应速度
        self.client = chromadb.EphemeralClient()
        
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            model=os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-m3")
        )
        
        self.llm = ChatOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            model=os.getenv("BASE_MODEL_ID", "Pro/zai-org/GLM-4.7"),
            temperature=0,
            request_timeout=60
        )
        self.ensemble_retriever = None
        self.reranker = SiliconFlowReranker(top_k=3)

    def ingest_pages(self, page_data: list):
        """
        全量 Markdown 页面索引
        """
        try:
            print(f"[*] Ingesting {len(page_data)} pages into memory...")
            documents = []
            for p in page_data:
                documents.append(Document(
                    page_content=p["markdown"],
                    metadata={"page": p["page"]}
                ))

            if not documents:
                return 0

            # 内存中创建临时向量库
            vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                client=self.client,
                collection_name=f"temp_idx_{int(time.time())}"
            )
            
            # 初始化 BM25
            bm25_retriever = BM25Retriever.from_documents(documents)
            bm25_retriever.k = 10  # Retrieve more for reranking

            # 构造混合检索器
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[vectorstore.as_retriever(search_kwargs={"k": 10}), bm25_retriever],
                weights=[0.6, 0.4]
            )
            
            print("[+] Hybrid index established in memory.")
            return len(documents)
        except Exception as e:
            print(f"[-] Ingest Error: {e}")
            raise e

    def query(self, question: str, history: list[dict] = []):
        if not self.ensemble_retriever:
            return {"answer": "系统尚未加载文档，请先上传。", "sources": []}

        # 0. Format History
        chat_history_str = ""
        for msg in history[-6:]:  # Keep last 6 messages context
            role = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '').replace('\n', ' ')
            chat_history_str += f"{role}: {content}\n"

        # 1. Standalone Question Generation (Query Rewriting)
        search_query = question
        if chat_history_str.strip():
            from langchain.chains.llm import LLMChain
            condense_template = """结合以下对话历史，将用户的后续问题改写为一个完整的、独立的搜索查询，以便于在文档中进行检索。
保持中文，不要回答问题，仅仅是改写问题使其包含上下文信息。

对话历史：
{chat_history}

后续问题：{question}

独立查询："""
            condense_prompt = PromptTemplate.from_template(condense_template)
            condense_chain = LLMChain(llm=self.llm, prompt=condense_prompt)
            
            try:
                print(f"[*] Rewriting query for context...")
                res = condense_chain.invoke({"chat_history": chat_history_str, "question": question})
                search_query = res["text"].strip()
                print(f"[+] Standalone Query: {search_query}")
            except Exception as e:
                print(f"[-] Query Rewrite Error: {e}, using original question.")

        # 2. First Pass: Hybrid Retrieval (Get top 10)
        try:
            initial_docs = self.ensemble_retriever.invoke(search_query)
        except Exception as e:
            print(f"[-] Retrieval Error: {e}")
            return {"answer": f"检索出错: {str(e)}", "sources": []}

        # 3. Second Pass: Reranking (Refine to top 3)
        final_docs = self.reranker.rerank(search_query, initial_docs)

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

        # Manual Chain Execution to allow custom doc list
        from langchain.chains.combine_documents.stuff import StuffDocumentsChain
        from langchain.chains.llm import LLMChain

        llm_chain = LLMChain(llm=self.llm, prompt=PROMPT)
        stuff_chain = StuffDocumentsChain(llm_chain=llm_chain, document_variable_name="context")

        try:
            response = stuff_chain.invoke({
                "input_documents": final_docs, 
                "question": question,
                "chat_history": chat_history_str
            })
            
            # Format sources
            sources = []
            for doc in final_docs:
                score_info = f" (Score: {doc.metadata.get('relevance_score', 'N/A')})"
                preview = doc.page_content[:150].replace('\n', ' ') + "..." + score_info
                sources.append(preview)

            return {
                "answer": response["output_text"],
                "sources": sources
            }
        except Exception as e:
            print(f"[-] Query Generation Error: {e}")
            return {"answer": f"生成回答出错: {str(e)}", "sources": []}

