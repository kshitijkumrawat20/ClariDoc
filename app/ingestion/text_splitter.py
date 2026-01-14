from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from uuid import uuid4
from typing import List, Dict
import os 
import json
from app.utils.metadata_utils import MetadataService
from app.metadata_extraction.metadata_ext import MetadataExtractor
from pydantic import BaseModel
from typing import Type
from app.utils.metadata_utils import MetadataService
class splitting_text:
    def __init__(self, documentTypeSchema:Type[BaseModel], llm=None, embedding_model=None):
        self.llm = llm 
        self.metadata_extractor = MetadataExtractor(llm = self.llm)
        self.metadata_services = MetadataService()
        self.documentTypeSchema = documentTypeSchema
        self.Keywordsfile_path = None
        self.embedding_model = embedding_model 

    def _clean_text(self, text:str)-> str: 
        """Clean extracted page content"""
        # remove excessive whitespace 
        text = " ".join(text.split())
        return text

    def text_splitting(self, doc: List[Document]) -> List[Document]:
        """Split document into chunks for processing"""

        all_chunks = []
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        
        # PERFORMANCE: Cache known_keywords in memory to avoid repeated file I/O
        known_keywords = None
        keywords_updated = False
        
        for i, page in enumerate(doc): 
            # reset per page
            try:
                text = page.get_text()
            except AttributeError:
                text = page.page_content

            

            if i == 0:
                print(f"Processing first page, setting up metadata extraction...")
                output_folder = "app/data/"
                filename = page.metadata['source'].replace(".","").replace("\\","")+ ".json"
                output_path = os.path.join(output_folder, filename)
                self.Keywordsfile_path = output_path
                # First page → extract + create JSON
                Document_metadata = self.metadata_extractor.extractMetadata(document=page, known_keywords={}, metadata_class=self.documentTypeSchema)
                extracted = Document_metadata.model_dump()
                normalized = MetadataService.normalize_dict_to_lists(metadata = extracted)

                with open(output_path, "w") as f:
                    json.dump(normalized, f, indent=4)
                known_keywords = normalized  # Cache in memory

            else:
                # PERFORMANCE: Use cached known_keywords instead of reading from file every time
                if known_keywords is None:
                    with open(self.Keywordsfile_path, "r") as f:
                        known_keywords = json.load(f)

                Document_metadata = self.metadata_extractor.extractMetadata(document=page, known_keywords=known_keywords, metadata_class=self.documentTypeSchema)

                # check if there is new keyword is added or not during metadata extraction if yes then normalise(convert to dict) and then add new values into the keys exist
                if Document_metadata.added_new_keyword:
                    new_data = self.metadata_services.normalize_dict_to_lists(
                    Document_metadata.model_dump(exclude_none= True)
                )
                    print(f"processing keywords update for page {i}")
                    new_data = MetadataService.keyword_sementic_check(new_data,known_keywords,embedding_model = self.embedding_model)
                    
                    for key,vals in new_data.items():
                        if isinstance(vals,list):
                            known_keywords[key] = list(set(known_keywords.get(key,[]) + vals))  #get the existing key and add vals and convert into set then list and update the file.
                    keywords_updated = True  # Mark for batch write

            # print(f"Document_metadata type: {type(Document_metadata)}")
            extracted_metadata = Document_metadata.model_dump(exclude_none=True)
            # print(f"extracted_metadata type: {type(extracted_metadata)}")
            print(f"doc number: {i}")


            if text.strip():
                uuid = str(uuid4())
                temp_doc = Document(
                    page_content=text,
                    metadata={
                        **page.metadata,
                        **extracted_metadata,
                        "page_no": i,
                        "doc_id": uuid,
                        "chunk_id": f"{uuid}_p{i}",
                        "type": "text"
                    }
                )
                chunks = splitter.split_documents([temp_doc])
                print(type(f"Type of chunks is: {chunks}"))
                all_chunks.extend(chunks)

        # PERFORMANCE: Batch write keywords only once at the end if updated
        if keywords_updated and known_keywords is not None:
            with open(self.Keywordsfile_path, "w") as f:
                json.dump(known_keywords, f, indent=4)

        return all_chunks
    

