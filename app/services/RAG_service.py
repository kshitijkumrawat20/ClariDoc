from app.utils.model_loader import ModelLoader
from app.ingestion.file_loader import FileLoader
from app.ingestion.text_splitter import splitting_text
from app.retrieval.retriever import Retriever
from app.embedding.embeder import QueryEmbedding
from app.embedding.vectore_store import VectorStore
from app.metadata_extraction.metadata_ext import MetadataExtractor
from app.utils.metadata_utils import MetadataService
from app.utils.logger import setup_logger
from langchain_core.documents import Document
import json
from langchain_community.retrievers import BM25Retriever
from threading import Lock

# Setup logger
logger = setup_logger(__name__)


class EmbeddingModelSingleton:
    """Thread-safe singleton for embedding model caching"""
    _instance = None
    _lock = Lock()
    _embedding_model = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_model(self):
        """Get or load the embedding model (thread-safe)"""
        if self._embedding_model is None:
            with self._lock:
                if self._embedding_model is None:
                    logger.info("Loading embedding model (one-time initialization)...")
                    embedding_loader = ModelLoader(model_provider="huggingface")
                    self._embedding_model = embedding_loader.load_llm()
        return self._embedding_model


# Singleton instance for model access
_model_singleton = EmbeddingModelSingleton()


class RAGService: 
    def __init__(self):
        logger.info("Initializing RAG service...")
        self._init_models()
        self.Docuement_Type = None 
        self.Pinecone_index = None
        self.Document_path = None
        self.Document_Type = None
        self.DocumentTypeScheme = None
        self.url = None
        self.chunks = None
        self.vector_store = None
        self.index = None
        self.namespace = None
        self.retriever = None
        self.metadataservice = MetadataService()
        logger.info("RAG service initialization complete")

    def _init_models(self):
        """Initialize LLM and embedding Models"""
        logger.info("Loading LLM model (openrouter)...")
        self.model_loader = ModelLoader(model_provider="openrouter")
        self.llm = self.model_loader.load_llm()
        logger.info("LLM model loaded successfully")
        logger.info("Loading embedding model (huggingface)...")
        self.embedding_model = _model_singleton.get_model()
        logger.info("Embedding model loaded successfully")

    def load_and_split_document(self, type:str, path:str= None, url:str = None):
        """Load and chunk document from local path or URL"""
        logger.info(f"Loading document. Type: {type}, Path: {path}, URL: {url}")
        file_loader = FileLoader(llm = self.llm)
        if type == "pdf":
            if path:
                logger.info(f"Loading PDF from path: {path}")
                doc = file_loader.load_pdf(path)
            elif url:
                logger.info(f"Loading PDF from URL: {url}")
                doc = file_loader.load_documents_from_url(url)
            else:
                logger.error("Either path or url must be provided for PDF")
                raise ValueError("Either path or url must be provided for PDF.")
        elif type == "word":
            if path:
                logger.info(f"Loading Word document from path: {path}")
                doc = file_loader.load_word_document(path)
            elif url:
                logger.error("URL loading not supported for Word documents")
                raise ValueError("URL loading not supported for Word documents.")
            else:
                logger.error("Path must be provided for Word document")
                raise ValueError("Path must be provided for Word document.")
        else:
            logger.error(f"Unsupported document type: {type}")
            raise ValueError("Unsupported document type. Use 'pdf' or 'word'.")
        
        logger.info("Detecting document type scheme...")
        self.DocumentTypeScheme = file_loader.detect_document_type(doc[0:2])
        logger.info(f"Document type scheme detected: {self.DocumentTypeScheme}")
        self.Document_Type = self.metadataservice.Return_document_model(self.DocumentTypeScheme)
        logger.debug(f"Document type model: {self.Document_Type}")
        self.splitter = splitting_text(documentTypeSchema=self.Document_Type, llm=self.llm, embedding_model=self.embedding_model)
        logger.info("Splitting document into chunks...")
        self.chunks = self.splitter.text_splitting(doc)
        logger.info(f"Total chunks created: {len(self.chunks)}")

    def create_query_embedding(self, query: str):
        logger.info("Creating query embedding...")
        self.query = query
        self.query_embedder = QueryEmbedding(query=query, embedding_model=self.embedding_model)
        self.query_embedding = self.query_embedder.get_embedding()
        logger.debug(f"Query embedding shape: {len(self.query_embedding) if hasattr(self.query_embedding, '__len__') else 'N/A'}")
        langchain_doc = Document(page_content=query)
        logger.info("Extracting metadata for the query...")
        self.metadataExtractor = MetadataExtractor(llm=self.llm)
        with open(self.splitter.Keywordsfile_path, "r") as f:
            known_keywords = json.load(f)
        raw_metadata = self.metadataExtractor.extractMetadata_query(self.Document_Type,langchain_doc, known_keywords = known_keywords)
        logger.debug(f"Query metadata extracted: {raw_metadata}")
        # Convert to dictionary and format for Pinecone
        metadata_dict = raw_metadata.model_dump(exclude_none=True)
        formatted_metadata = self.metadataservice.format_metadata_for_pinecone(metadata_dict)
        
        # Remove problematic fields that cause serialization issues
        self.query_metadata = {
            k: v for k, v in formatted_metadata.items() 
            if k not in ["obligations", "exclusions", "notes", "added_new_keyword"]
        }
    
        logger.debug(f"Query metadata formatted for search")

    def create_vector_store(self):
        logger.info("Creating vector store...")
        self.vector_store_class_instance = VectorStore(self.chunks, self.embedding_model)
        self.index, self.namespace, self.vector_store = self.vector_store_class_instance.create_vectorestore()
        logger.info(f"Vector store created with namespace: {self.namespace}")
        ### Sparse Retriever(BM25)
        self.sparse_retriever=BM25Retriever.from_documents(self.chunks)
        self.sparse_retriever.k=3 ##top- k documents to retriever

        

    def retrive_documents(self, raw_query: str):
        logger.info("Retrieving documents from vector store...")
        self.create_query_embedding(raw_query)
        
        self.retriever = Retriever(self.index,raw_query,self.query_metadata, self.namespace, self.vector_store,sparse_retriever = self.sparse_retriever,llm = self.llm)
        self.result = self.retriever.retrieval_from_pinecone_vectoreStore()
    
    def answer_query(self, raw_query:str) -> str:
        """Answer user query using retrieved documents and LLM"""
        logger.info(f"Answering query: {raw_query}")
        context_clauses = [doc.page_content for doc in self.result]

        logger.debug(f"Using {len(context_clauses)} context clauses")

        prompt = f"""
        You are a legal/insurance domain expert and policy analyst. 
        Use the following extracted clauses from policy documents to answer the question.  
        If you can't find the answer, say "I don't know".
        Context clauses:
        {"".join(context_clauses)}
        Question: {raw_query}
        """
        logger.info("Invoking LLM to generate answer...")
        response = self.llm.invoke(prompt)
        logger.debug("LLM response received")
        
        # Extract string content from response object
        if hasattr(response, 'content'):
            return response.content
        elif isinstance(response, str):
            return response
        else:
            return str(response)