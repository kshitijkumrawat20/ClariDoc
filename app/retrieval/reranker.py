from typing import List, Optional
from langchain_core.documents import Document
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser 

class Reranker:
    """Reranker class to rerank retrieved documents based on relevance to the query."""
    def __init__(self,llm, retrieved_docs:List[Document],query:str) ->List[Document]:
        self.llm = llm
        self.retrieved_docs = retrieved_docs
        self.query = query

    def rerank_documents(self) -> List[Document]:
        """
        Rerank the retrieved documents based on their relevance to the query.
        
        Args:
            retrieved_docs: List of Document objects retrieved from the retriever.
            query: The original user query string.
        
        Returns:
            List of Document objects sorted by relevance to the query.
        """
        # Create a prompt template for scoring
       # Prompt Template
        prompt_template = PromptTemplate.from_template("""
        You are a helpful assistant. Your task is to rank the following documents from most to least relevant to the user's question.

        User Question: "{question}"

        Documents:
        {documents}

        Instructions:
        - Think about the relevance of each document to the user's question.
        - Return a list of document indices in ranked order, starting from the most relevant.

        Output format: comma-separated document indices (e.g., 2,1,3,0,...)
        """)

        chain=prompt_template | self.llm | StrOutputParser()
        doc_texts = [f"{i+1}. {doc.page_content}" for i,doc in enumerate(self.retrieved_docs)]
        response = chain.invoke({
            "question": self.query,
            "documents": "\n".join(doc_texts)
        })
        ranked_indices = [int(i) for i in response.split(",")]
        return [self.retrieved_docs[i-1] for i in ranked_indices]