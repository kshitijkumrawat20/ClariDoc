# from config_loader import 
import os 
from pydantic import BaseModel, Field
from typing import Literal, Optional,Any
from app.utils.config_loader import load_config
from app.utils.logger import setup_logger
from langchain_groq import ChatGroq 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.chat_models import init_chat_model

logger = setup_logger(__name__)

class ConfigLoader:
    def __init__(self):
        logger.debug("Loading configuration...")
        self.config = load_config()

    def __getitem__(self,key):## This method allows you to access config values using dictionary-like syntax
        return self.config[key]
    

class ModelLoader(BaseModel):
    model_provider: Literal["groq", "gemini", "openai","gemini_lite", "huggingface","openrouter"] = "openrouter" 
    config: Optional[ConfigLoader] = Field(default = None, exclude = True) # either the config is ConfigLoader object or None

    def model_post_init(self, __context: Any)->None:
        self.config = ConfigLoader()   # Automatically ensures that whenever you create ModelLoader, it loads the config.. model_post_init is a Pydantic V2 hook, which runs after model creation.It assigns a ConfigLoader() instance to self.config.This ensures the configuration is loaded whenever you create a ModelLoader.

    class Config:
        arbitrary_types_allowed = True  # Allows ConfigLoader (a non-Pydantic class) to be used as a field in the model.

    def load_llm(self):
        """
        Load and return the LLM model
        """
        logger.info(f"Loading LLM model from provider: {self.model_provider}")
        if self.model_provider == "groq":
            groq_api_key = os.getenv("GROQ_API_KEY")
            model_name = self.config["llm"]["groq"]["model_name"]
            llm = ChatGroq(model = model_name, api_key = groq_api_key)
            
        elif self.model_provider =="gemini":
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            model_name = self.config["llm"]["gemini"]["model_name"]
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key= gemini_api_key
            )
        elif self.model_provider =="gemini_lite":
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            model_name = self.config["llm"]["gemini_lite"]["model_name"]
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key= gemini_api_key
            )
        elif self.model_provider =="openai":
            api_key = os.getenv("OPENAI_API_KEY")
            model_name = self.config["embedding_model"]["openai"]["model_name"]
            llm = OpenAIEmbeddings(model=model_name, api_key = api_key)
        elif self.model_provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            model_name = self.config["llm"]["openrouter"]["model_name"]
            llm = init_chat_model(
                model="google/gemma-3-27b-it:free",
                model_provider="openai",
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
        elif self.model_provider =="huggingface":
            api_key = os.getenv("HF_TOKEN")
            model_name = self.config["embedding_model"]["huggingface"]["model_name"]
            # Pass token directly to model if needed, avoid modifying os.environ
            llm = HuggingFaceEmbeddings(model=model_name)
        else: 
            logger.error(f"Unsupported model provider: {self.model_provider}")
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
        
        logger.info(f"Successfully loaded {self.model_provider} model")
        return llm


    
         