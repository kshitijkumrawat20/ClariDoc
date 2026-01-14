import uuid
from typing import Dict, Optional
from datetime  import datetime, timedelta
from app.services.RAG_service import RAGService

class Session:
    def __init__(self, session_id:str):
        self.session_id = session_id 
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.rag_service : Optional[RAGService] = None
        self.document_uploaded = False
        self.vector_store_created = False
        self.document_info = {}

    def update_activity(self):
        self.last_activity = datetime.now()

    def is_expired(self, timeout_minutes: int = 60) -> bool:
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def create_session(self) -> str:
        session_id  = str(uuid.uuid4())
        self.sessions[session_id] = Session(session_id)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if not session.is_expired():
                session.update_activity()
                return session
            else:
                del self.sessions[session_id]
        return None
    
    def delete_session(self, session_id:str): 
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def cleanup_expired_sessions(self): 
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if session.is_expired()
        ]
        for sid in expired_sessions:
            del self.sessions[sid]

session_manager = SessionManager()

