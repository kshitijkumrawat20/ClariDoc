import os
from pinecone import Pinecone
from pinecone import ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from datetime import datetime
from uuid import uuid4

class VectorStore:
    def __init__(self, text_chunks, embedding_model):
        self.text_chunks = text_chunks
        self.current_time = datetime.now()
        self.embedding_model = embedding_model

    def create_vectorestore(self):
        pinecone_key = os.getenv("PINECONE_API_KEY")
        pc = Pinecone(api_key=pinecone_key)  
        time_string = self.current_time.strftime("%Y-%m-%d-%H-%M")
        index_name = "rag-project"
        namespace = f"rag-project{time_string}"
        if not pc.has_index(index_name):
            pc.create_index(
                name=index_name,
                dimension=1024,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )

        index = pc.Index(index_name)
        uuids = [str(uuid4()) for _ in range(len(self.text_chunks))]
        vector_store = PineconeVectorStore.from_documents(
            documents=self.text_chunks,
            index_name=index_name, 
            embedding=self.embedding_model, 
            namespace=namespace
        )

        return index, namespace, vector_store


