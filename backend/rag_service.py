import os
import logging  # 添加缺失的logging导入
from pathlib import Path
from typing import List, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document


class RAGService:
    def __init__(self, embeddings_model: str = "text-embedding-v1"):
        # 初始化logger
        self.logger = logging.getLogger(__name__)

        # 初始化配置
        self.embeddings = DashScopeEmbeddings(
            model=embeddings_model,
            dashscope_api_key=os.getenv('DASHSCOPE_API_KEY')
        )
        self.vector_db = None
        self.text_db = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n\n", "\n", "。", "！", "？", "，", "、", ""]
        )

    def init_rag(self, data_dir: str = "story_data") -> dict:
        """初始化RAG系统"""
        self.logger.info(f"正在初始化 RAG 系统，数据目录: {data_dir}")

        os.makedirs(data_dir, exist_ok=True)

        try:
            documents = self._load_documents(data_dir)
            if not documents:
                self.logger.warning(f"数据目录 {data_dir} 中没有找到任何文本文件")
                return {"status": "no_files"}

            self.logger.info(f"加载了 {len(documents)} 个文档")

            chunks = self.text_splitter.split_documents(documents)
            self.logger.info(f"分割为 {len(chunks)} 个文本块")

            self._create_retrievers(chunks)
            self.logger.info("RAG 系统初始化成功")

            return {
                "status": "success",
                "chunk_count": len(chunks),
                "file_count": len(set(d.metadata["source"] for d in chunks))
            }
        except Exception as e:
            self.logger.error(f"RAG 初始化失败: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def _load_documents(self, data_dir: str) -> List[Document]:
        """加载目录中的所有文本文件"""
        documents = []
        for file_path in Path(data_dir).glob("**/*.txt"):
            try:
                loader = TextLoader(str(file_path), encoding='utf-8')
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = str(file_path.relative_to(data_dir))
                documents.extend(docs)
            except Exception as e:
                self.logger.warning(f"跳过文件 {file_path}: {str(e)}")
        return documents

    def _create_retrievers(self, chunks: List[Document]):
        """创建向量检索和关键词检索器"""
        self.vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory="vector_db"
        )

        texts = [doc.page_content for doc in chunks]
        self.text_db = BM25Retriever.from_texts(
            texts,
            metadatas=[doc.metadata for doc in chunks]
        )

    def get_retriever(self, top_k: int = 3) -> EnsembleRetriever:
        """获取混合检索器"""
        return EnsembleRetriever(
            retrievers=[
                self.vector_db.as_retriever(search_kwargs={"k": top_k}),
                self.text_db
            ],
            weights=[0.5, 0.5]
        )

    def search(self, query: str, top_k: int = 3) -> List[Document]:
        """执行检索"""
        if not self.vector_db or not self.text_db:
            raise ValueError("RAG系统未初始化")

        retriever = self.get_retriever(top_k)
        try:
            # 优先使用新的invoke方法
            return retriever.invoke(query)
        except AttributeError:
            # 兼容旧版本
            return retriever.get_relevant_documents(query)