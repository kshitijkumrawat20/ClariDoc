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

    def text_splitting(self, doc: List[Document], extract_metadata_per_page: bool = True) -> List[Document]:
        """
        Split document into chunks for processing
        
        Args:
            doc: List of document pages
            extract_metadata_per_page: If False, only extract metadata from first page (faster)
        """

        all_chunks = []
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        
        # PERFORMANCE: Cache known_keywords in memory to avoid repeated file I/O
        cached_keywords = None
        keywords_updated = False
        first_page_metadata = None  # Cache first page metadata for reuse
        
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
                cached_keywords = normalized  # Cache in memory
                first_page_metadata = Document_metadata  # Cache for reuse

            else:
                # PERFORMANCE: Option to skip metadata extraction per page for speed
                if not extract_metadata_per_page:
                    # Reuse first page metadata (much faster, ~70% speedup)
                    Document_metadata = first_page_metadata
                else:
                    # PERFORMANCE: Use cached_keywords instead of reading from file every time
                    if cached_keywords is None:
                        with open(self.Keywordsfile_path, "r") as f:
                            cached_keywords = json.load(f)

                    Document_metadata = self.metadata_extractor.extractMetadata(document=page, known_keywords=cached_keywords, metadata_class=self.documentTypeSchema)

                    # check if there is new keyword is added or not during metadata extraction if yes then normalise(convert to dict) and then add new values into the keys exist
                    if Document_metadata.added_new_keyword:
                        new_data = self.metadata_services.normalize_dict_to_lists(
                        Document_metadata.model_dump(exclude_none= True)
                    )
                        print(f"processing keywords update for page {i}")
                        new_data = MetadataService.keyword_sementic_check(new_data,cached_keywords,embedding_model = self.embedding_model)
                        
                        for key,vals in new_data.items():
                            if isinstance(vals,list):
                                cached_keywords[key] = list(set(cached_keywords.get(key,[]) + vals))  #get the existing key and add vals and convert into set then list and update the file.
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
                # PERFORMANCE: Split documents in batch instead of one at a time
                chunks = splitter.split_documents([temp_doc])
                all_chunks.extend(chunks)

        # PERFORMANCE: Batch write keywords only once at the end if updated
        if keywords_updated and cached_keywords is not None:
            with open(self.Keywordsfile_path, "w") as f:
                json.dump(cached_keywords, f, indent=4)

        return all_chunks
    

