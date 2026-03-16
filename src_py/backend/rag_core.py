"""
RAG 核心模块 —— 向量数据库管理与检索。
"""

import os
import json
import requests
import chromadb
import pandas as pd
from typing import List

from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document


class HTTPEmbeddings(Embeddings):
    """通用 HTTP Embedding 封装"""

    def __init__(self, endpoint: str, model: str = None, api_key: str = None, host: str = None, timeout: int = 100):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.host = host
        self.timeout = timeout
        print(f"[HTTPEmbeddings] 初始化，Endpoint: {self.endpoint}, Model: {self.model}, Host: {self.host}")

    def _post(self, texts: List[str]) -> List[List[float]]:
        payload = {"input": texts[0]}
        if self.model:
            payload["model"] = self.model

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.host:
            headers["Host"] = self.host

        resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        #data = [item["embedding"] for item in data["data"]]
        print(data)
        return data

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            vecs = self._post([t])
            if not vecs:
                raise ValueError("Embedding 接口未返回向量")
            results.append(vecs[0])
        return results

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


class RAGManager:
    """RAG 管理核心类"""

    def __init__(self, embed_api_url: str, embed_api_key: str = None, embed_model_name: str = None, embed_host: str = None):
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        self.persist_directory = os.path.join(base_dir, "chroma_db")

        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
        except Exception as e:
            print(f"[致命错误] 无法初始化 ChromaDB 客户端: {e}")
            raise

        embedding_endpoint = embed_api_url.rstrip("/")
        print(f"[RAG] 初始化 Embedding 服务，连接地址: {embedding_endpoint}")

        try:
            if embedding_endpoint:
                self.embedding_fn = HTTPEmbeddings(
                    endpoint=embedding_endpoint,
                    model=embed_model_name,
                    api_key=embed_api_key,
                    host=embed_host,
                )
            else:
                self.embedding_fn = None
                print("[RAG] Embedding endpoint is empty. Skipping initialization.")
        except Exception as e:
            print(f"[RAG] Embedding 模型初始化失败: {e}")
            self.embedding_fn = None


    def update_embeddings(self, embed_api_url: str, embed_api_key: str = None, embed_model_name: str = None, embed_host: str = None):
        """动态更新 Embedding 配置"""
        embedding_endpoint = embed_api_url.rstrip("/")
        try:
            self.embedding_fn = HTTPEmbeddings(
                endpoint=embedding_endpoint,
                model=embed_model_name,
                api_key=embed_api_key,
                host=embed_host,
            )
            print(f"[RAG] Embedding 服务已更新，模型: {embed_model_name}, 地址: {embedding_endpoint}")
        except Exception as e:
            print(f"[RAG] Embedding 配置更新失败: {e}")
            self.embedding_fn = None

    @property
    def knowledge_bases(self):
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            print(f"获取知识库列表失败: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  默认知识库
    # ------------------------------------------------------------------ #
    def init_default_kb(self):
        default_kb_name = "GJB_5369_2005"
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        json_path = os.path.join(base_dir, "GJB", "rules.json")

        if default_kb_name in self.knowledge_bases:
            return
        if not os.path.exists(json_path):
            print(f"[RAG] 未找到 {json_path}，跳过默认知识库初始化。")
            return

        print(f"[RAG] 正在初始化默认知识库: {default_kb_name} ...")
        try:
            formatted_text = ""
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    formatted_text += (
                        f"规则ID: {item.get('rule_id', 'N/A')}\n"
                        f"规则分类: {item.get('title', '未知')}\n"
                        f"强制属性: {item.get('rule_property', '未知')}\n"
                        f"规则内容: {item.get('rule', '')}\n"
                        f"{'-' * 30}\n\n"
                    )
            temp_path = "temp_gjb_rules.txt"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(formatted_text)
            self.add_to_kb(temp_path, default_kb_name)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            print(f"[RAG] 解析 rules.json 出错: {e}")

    # ------------------------------------------------------------------ #
    #  知识库操作
    # ------------------------------------------------------------------ #
    def add_to_kb(self, file_path, kb_name):
        if not os.path.exists(file_path):
            return False, "文件路径不存在"
        if not kb_name:
            kb_name = "default_kb"

        try:
            print(f"[RAG] 正在读取文件: {file_path}")
            splits = []

            if file_path.endswith((".xlsx", ".xls")):
                splits = self._load_excel_row_by_row(file_path)
                print(f"[RAG] Excel 处理完毕，共 {len(splits)} 行数据作为片段。")
            else:
                if file_path.endswith(".md"):
                    loader = UnstructuredMarkdownLoader(file_path)
                else:
                    loader = TextLoader(file_path, encoding="utf-8", autodetect_encoding=True)
                docs = loader.load()
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=800,
                    chunk_overlap=100,
                    separators=["-{30}", "\n\n", "\n"],
                )
                splits = text_splitter.split_documents(docs)

            if splits:
                print(f"[RAG] 正在存入知识库: {kb_name}")
                Chroma.from_documents(
                    documents=splits,
                    embedding=self.embedding_fn,
                    client=self.client,
                    collection_name=kb_name,
                )
                return True, f"成功！{len(splits)} 个片段已存入知识库 '{kb_name}'。"
            return False, "未能从文件中提取到有效内容。"
        except Exception as e:
            print(f"[RAG] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)

    def delete_kb(self, kb_name):
        try:
            self.client.delete_collection(kb_name)
            return True
        except Exception as e:
            print(f"删除失败: {e}")
            return False

    def reset_database(self):
        try:
            collections = self.client.list_collections()
            if not collections:
                return True, "数据库已经是空的。"
            for collection in collections:
                self.client.delete_collection(collection.name)
            return True, "所有知识库已成功清空（Collection已移除）。"
        except Exception as e:
            print(f"[RAG] 重置数据库失败: {e}")
            return False, f"重置失败: {str(e)}"

    def recall(self, query, kb_name):
        existing_kbs = [c.name for c in self.client.list_collections()]
        if kb_name not in existing_kbs:
            return f"（未找到知识库：{kb_name}）"

        print(f"[RAG] 正在知识库 [{kb_name}] 中检索: {query}")
        try:
            vector_db = Chroma(
                client=self.client,
                collection_name=kb_name,
                embedding_function=self.embedding_fn,
            )
            results = vector_db.similarity_search(query, k=3)
            context_str = ""
            for i, doc in enumerate(results):
                context_str += f"\n/* --- 参考片段 {i + 1} --- */\n{doc.page_content}\n"
            return context_str
        except Exception as e:
            return f"（检索出错: {e}）"

    def recall_multi(self, query, kb_names):
        """从多个知识库检索并合并结果"""
        combined = []
        for kb_name in kb_names:
            res = self.recall(query, kb_name)
            if res and "未找到" not in res and "检索出错" not in res:
                combined.append(f"【参考规范/文档来源: {kb_name}】\n{res}")
        if combined:
            return "\n\n".join(combined)
        return "（已启用 RAG，但未在选定知识库中检索到高相关性内容）"

    # ------------------------------------------------------------------ #
    #  私有方法
    # ------------------------------------------------------------------ #
    def _load_excel_row_by_row(self, file_path):
        docs = []
        try:
            df = pd.read_excel(file_path).fillna("")
            columns = df.columns.tolist()
            for index, row in df.iterrows():
                content_parts = []
                for col in columns:
                    val = str(row[col]).strip()
                    if val:
                        content_parts.append(f"{col}: {val}")
                row_content = "\n".join(content_parts)
                if row_content:
                    docs.append(
                        Document(
                            page_content=row_content,
                            metadata={"source": file_path, "row_index": index},
                        )
                    )
            return docs
        except Exception as e:
            print(f"[Excel Error] 读取失败: {e}")
            raise
