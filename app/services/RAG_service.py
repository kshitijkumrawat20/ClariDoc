from app.utils.model_loader import ModelLoader
from app.ingestion.file_loader import FileLoader
from app.ingestion.text_splitter import splitting_text
from app.retrieval.retriever import Retriever
from app.embedding.embeder import QueryEmbedding
from app.embedding.vectore_store import VectorStore
from app.metadata_extraction.metadata_ext import MetadataExtractor
from app.utils.metadata_utils import MetadataService
from langchain_core.documents import Document
import json
from langchain_community.retrievers import BM25Retriever
from langchain.schema import Document

# Global model instances (loaded once)
_embedding_model = None

def get_models():
    global  _embedding_model
    if _embedding_model is None:
        print("Loading models (one-time initialization)...")
        embedding_loader = ModelLoader(model_provider="huggingface")
        _embedding_model = embedding_loader.load_llm()
    return _embedding_model

class RAGService: 
    def __init__(self):
        print("[RAGService] Initializing service...")
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
        print("[RAGService] Initialization complete.")

    def _init_models(self):
        """Initialize LLM and embedding Models"""
        print("[RAGService] Loading LLM model (openrouter)...")
        self.model_loader = ModelLoader(model_provider="openrouter")
        self.llm = self.model_loader.load_llm()
        print("[RAGService] LLM model loaded.")
        print("[RAGService] Loading embedding model (huggingface)...")
        # self.model_loader = ModelLoader(model_provider="huggingface")
        self.embedding_model = get_models()
        print("[RAGService] Embedding model loaded.")

    def load_and_split_document(self, type:str, path:str= None, url:str = None):
        """Load and chunk document from local path or URL"""
        print(f"[RAGService] Loading document. Type: {type}, Path: {path}, URL: {url}")
        file_loader = FileLoader(llm = self.llm)
        if type == "pdf":
            if path:
                print(f"[RAGService] Loading PDF from path: {path}")
                doc = file_loader.load_pdf(path)
            elif url:
                print(f"[RAGService] Loading PDF from URL: {url}")
                doc = file_loader.load_documents_from_url(url)
            else:
                print("[RAGService] Error: Either path or url must be provided for PDF.")
                raise ValueError("Either path or url must be provided for PDF.")
        elif type == "word":
            if path:
                print(f"[RAGService] Loading Word document from path: {path}")
                doc = file_loader.load_word_document(path)
            elif url:
                print("[RAGService] Error: URL loading not supported for Word documents.")
                raise ValueError("URL loading not supported for Word documents.")
            else:
                print("[RAGService] Error: Path must be provided for Word document.")
                raise ValueError("Path must be provided for Word document.")
        else:
            print("[RAGService] Error: Unsupported document type.")
            raise ValueError("Unsupported document type. Use 'pdf' or 'word'.")
        
        print("[RAGService] Detecting document type scheme...")
        self.DocumentTypeScheme = file_loader.detect_document_type(doc[0:2])
        print(f"[RAGService] Document type scheme detected: {self.DocumentTypeScheme}")
        self.Document_Type = self.metadataservice.Return_document_model(self.DocumentTypeScheme)
        print(f"[RAGService] Document type model: {self.Document_Type}")
        self.splitter = splitting_text(documentTypeSchema=self.Document_Type, llm=self.llm, embedding_model=self.embedding_model)
        print("[RAGService] Splitting document into chunks...")
        self.chunks = self.splitter.text_splitting(doc)
        print(f"[RAGService] Total chunks created: {len(self.chunks)}")

    def create_query_embedding(self, query: str):
        print("[RAGService] Creating query embedding...")
        self.query = query
        self.query_embedder = QueryEmbedding(query=query, embedding_model=self.embedding_model)
        self.query_embedding = self.query_embedder.get_embedding()
        print(f"[RAGService] Query embedding created: {self.query_embedding}")
        langchain_doc = Document(page_content=query)
        print("[RAGService] Extracting metadata for the query...")
        self.metadataExtractor = MetadataExtractor(llm=self.llm)
        with open(self.splitter.Keywordsfile_path, "r") as f:
            known_keywords = json.load(f)
        raw_metadata = self.metadataExtractor.extractMetadata_query(self.Document_Type,langchain_doc, known_keywords = known_keywords)
        print(f"[RAGService] Query metadata extracted: {raw_metadata}")
        # Convert to dictionary and format for Pinecone
        metadata_dict = raw_metadata.model_dump(exclude_none=True)
        formatted_metadata = self.metadataservice.format_metadata_for_pinecone(metadata_dict)
        
        # Remove problematic fields that cause serialization issues
        self.query_metadata = {
            k: v for k, v in formatted_metadata.items() 
            if k not in ["obligations", "exclusions", "notes", "added_new_keyword"]
        }
    
        print(f"[RAGService] Query metadata type: {type(self.query_metadata)}")
        print(f"[RAGService] Query metadata: {self.query_metadata}")

    def create_vector_store(self):
        print("[RAGService] Creating vector store...")
        self.vector_store_class_instance = VectorStore(self.chunks, self.embedding_model)
        self.index, self.namespace, self.vector_store = self.vector_store_class_instance.create_vectorestore()
        print(f"[RAGService] Vector store created. Index: {self.index}, Namespace: {self.namespace}")
        ### Sparse Retriever(BM25)
        self.sparse_retriever=BM25Retriever.from_documents(self.chunks)
        self.sparse_retriever.k=3 ##top- k documents to retriever

        

    def retrive_documents(self, raw_query: str):
        print("[RAGService] Retrieving documents from vector store...")
        self.create_query_embedding(raw_query)
        
        self.retriever = Retriever(self.index,raw_query,self.query_metadata, self.namespace, self.vector_store,sparse_retriever = self.sparse_retriever,llm = self.llm)
        self.result = self.retriever.retrieval_from_pinecone_vectoreStore()
        # self.result = self.retriever.invoke(raw_query)
        # print(f"[RAGService] Retrieval result: {self.result}")
    
    def answer_query(self, raw_query:str) -> str:
        """Answer user query using retrieved documents and LLM"""
        print(f"[RAGService] Answering query: {raw_query}")
        # top_clause = self.result['matches']
        # top_clause_dicts = [r.to_dict() for r in top_clause]
        # self.top_clauses = top_clause_dicts
        # keys_to_remove = {"file_path", "source", "producer", "keywords", "subject", "added_new_keyword", "author", "chunk_id"}
        # for r in top_clause_dicts:
        #     meta = r.get("metadata", {})
        #     for k in keys_to_remove:
        #         meta.pop(k, None)

        # context_clauses = json.dumps(top_clause_dicts, separators=(",", ":"))
        context_clauses = [doc.page_content for doc in self.result]

        print(f"context_clauses: {context_clauses}")

        prompt = f"""
        You are a legal/insurance domain expert and policy analyst. 
        Use the following extracted clauses from policy documents to answer the question.  
        If you can't find the answer, say "I don't know".
        Context clauses:
        {"".join(context_clauses)}
        Question: {raw_query}
        """
        print("[RAGService] Invoking LLM with prompt...")
        response = self.llm.invoke(prompt)
        print(f"[RAGService] LLM response: {response}")
        
        # Extract string content from response object
        if hasattr(response, 'content'):
            return response.content
        elif isinstance(response, str):
            return response
        else:
            return str(response)