import json
from langchain_core.exceptions import OutputParserException
from langchain_core.documents import Document
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from typing import Type
from pydantic import BaseModel
from threading import Lock

# wrap parser with fixer once
# pydantic_parser = PydanticOutputParser(pydantic_object=InsuranceMetadata)
# fixing_parser = OutputFixingParser.from_llm(llm=llm, parser=pydantic_parser) 


class MetadataExtractor:
    def __init__(self, llm = None):
        self.llm = llm
        # PERFORMANCE: Cache schema serialization to avoid repeated JSON dumps
        self._schema_cache = {}
        self._cache_lock = Lock()  # Thread-safe cache access

    def _get_cached_schema(self, metadata_class: Type[BaseModel]) -> str:
        """Get cached JSON schema or compute and cache it (thread-safe)"""
        class_name = metadata_class.__name__
        if class_name not in self._schema_cache:
            with self._cache_lock:
                # Double-check pattern for thread safety
                if class_name not in self._schema_cache:
                    self._schema_cache[class_name] = json.dumps(
                        metadata_class.model_json_schema(), 
                        indent=2
                    )
        return self._schema_cache[class_name]

    def extractMetadata_query(self, metadata_class : Type[BaseModel],document: Document, known_keywords: dict) -> BaseModel:
        parser = PydanticOutputParser(pydantic_object=metadata_class)

        # PERFORMANCE: Use cached schema instead of recomputing
        schema_str = self._get_cached_schema(metadata_class)
        keywords_str = json.dumps(known_keywords, indent=2)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an information extraction system. 
            Extract only the required metadata from the user query using the existing known keywords. 

            ⚠️ CRITICAL FORMATTING RULES:
            - ALL fields must be arrays/lists, even if there's only one value
            - For single values, wrap in brackets: "doc_id": ["single_value"]
            - For multiple values: "coverage_type": ["value1", "value2", "value3"]
            - For null/empty fields, use: null (not empty arrays)
            
            ⚠️ Content Rules:
            - For exclusions and obligations, DO NOT copy full sentences. 
            - Instead, extract only concise normalized keywords (2–5 words max each).
            - Use existing keywords if they already exist in the provided list.
            - Prefer to reuse existing keywords if they are semantically the same.  
            - If you find a new keyword that is a sub-type or more specific variant of an existing one, keep both:  
            reuse the closest match from existing keywords, and also add the new one.  
            - In that case, set added_new_keyword=true.
            - Do not include raw paragraphs in the output.
             
            Schema you must follow:
            {schema}

            Existing Keywords:
            {keywords}
            """),
            ("human", "Text:\n{document_content}")
        ])
        chain = prompt | self.llm | parser

        try:
            result = chain.invoke({
                "schema": schema_str,
                "keywords": keywords_str,
                "document_content": document.page_content
            })
            return result
        except OutputParserException as e:
            print(f"⚠️ Parser failed on doc {document.metadata.get('source')} | error: {e}")
            return metadata_class(added_new_keyword=False)
    
    def extractMetadata(self, metadata_class : Type[BaseModel], document: Document, known_keywords: dict = None) -> BaseModel:
        parser = PydanticOutputParser(pydantic_object=metadata_class)

        # PERFORMANCE: Use cached schema instead of recomputing
        schema_str = self._get_cached_schema(metadata_class)
        # keywords_str = json.dumps(known_keywords, indent=2)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an information extraction system. 
            Extract only the required metadata from the text according to schema given below. 

            ⚠️ CRITICAL FORMATTING RULES:
            - ALL fields must be arrays/lists, even if there's only one value
            - For single values, wrap in brackets: "doc_id": ["single_value"]
            - For multiple values: "coverage_type": ["value1", "value2", "value3"]
            - For null/empty fields, use: null (not empty arrays)
            
            ⚠️ Content Rules:
            - For exclusions and obligations, DO NOT copy full sentences. 
            - Instead, extract only concise normalized keywords (2–5 words max each).
            - Do not include raw paragraphs in the output.
            - always keep added_new_keyword as True. 
            
            Schema you must follow:
            {schema}

            
            """),
            ("human", "Text:\n{document_content}")
        ])
        # - Instead, extract only concise normalized keywords (2–5 words max each).
        #     - Use existing keywords if they already exist in the provided list.
        #     - Prefer to reuse existing keywords if they are semantically the same.  
        #     - If you find a new keyword that is a **sub-type** or **more specific variant** of an existing one, keep both:  
        #     *reuse the closest match from existing keywords*, and also add the new one.  
        #     - In that case, set `added_new_keyword=true`.
        # Existing Keywords:
            # {keywords}
        
        # PERFORMANCE: Use lower temperature for faster, more deterministic responses
        chain = prompt | self.llm.bind(temperature=0.1) | parser

        try:
            result = chain.invoke({
                "schema": schema_str,
                # "keywords": keywords_str,
                "document_content": document.page_content
            })
            return result
        except OutputParserException as e:
            print(f"⚠️ Parser failed on doc {document.metadata.get('source')} | error: {e}")
            return metadata_class(added_new_keyword=True)   # instantiate fallback