from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
import os 
import tempfile
from pathlib import Path
from app.core.session_manager import SessionManager, Session, session_manager
from app.services.RAG_service import RAGService
from app.schemas.request_models import QueryRequest
from app.schemas.response_models import SessionResponse, QueryResponse, UploadResponse, SourceDocument
from app.config.config import get_settings
from app.utils.input_validator import sanitize_filename, validate_session_id, sanitize_query
from app.utils.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)

def get_session(session_id:str) -> Session:
    """Dependency to get and validate session"""
    # Validate session ID format
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    session = session_manager.get_session(session_id=session_id)
    if not session: 
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session

@router.post("/session", response_model=SessionResponse)
async def create_session():
    """Create a new session for document processing"""
    session_id = session_manager.create_session()
    logger.info(f"Created new session: {session_id}")
    return SessionResponse(
        session_id=session_id,
        message="Session created successfully"
    )

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if not validate_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    session_manager.delete_session(session_id)
    logger.info(f"Deleted session: {session_id}")
    return {"message": "Session deleted successfully"}

@router.post("/upload/{session_id}", response_model=UploadResponse)
async def upload_document(
    session_id:str, 
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    session: Session = Depends(get_session)
):
    """Upload and process a document"""
    settings = get_settings()
    
    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    
    # validate file type
    file_extension = Path(safe_filename).suffix.lower()
    if file_extension not in settings.allowed_file_types:
        raise HTTPException(
            status_code=400,
            detail = f"File type {file_extension} is not allowed"
        )
     #Validate file size
    if file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size too large. Maximum size: {settings.max_file_size} bytes"
        )
    try:
        # create upload dir if not exist
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(exist_ok=True)

        # saving temporarily 
        with tempfile.NamedTemporaryFile(delete= False, suffix = file_exension) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Initialize RAG service for this session 
        session.rag_service = RAGService()

        # Load and split document
        session.rag_service.load_and_split_document(
            type = doc_type, 
            path = tmp_file_path
        ) 

        # create vectore store 
        session.rag_service.create_vector_store()

        # update session state 

        session.document_uploaded = True
        session.vector_store_created = True
        session.document_info = {
            "filename": file.filename,
            "type": doc_type,
            "size": file.size,
            "chunks_count": len(session.rag_service.chunks)
        }
        # Clean up temporary file
        os.unlink(tmp_file_path)

        return UploadResponse(
            session_id=session_id,
            filename=file.filename,
            document_type=doc_type,
            chunks_created=len(session.rag_service.chunks),
            message="Document uploaded and processed successfully"
        )
    except Exception as e:
        # Clean up temporary file if it exists
        if 'temp_file_path' in locals():
            try:
                os.unlink(tmp_file_path)
            except OSError:
                pass
        logger.error(f"Error processing document upload for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing document")

@router.post("/query/{session_id}", response_model = QueryResponse)
async def query_document(
    session_id: str, 
    query_request: QueryRequest,
    session: Session = Depends(get_session)
):
    """Query the uploaded Document"""
    if not session.document_uploaded or not session.vector_store_created:
        raise HTTPException(
            status_code=400,
            detail="No document uploaded or processed for this session"
        )
    
    # Sanitize query input
    sanitized_query = sanitize_query(query_request.query)
    if not sanitized_query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )
    
    try: 
        # create query embedding (use sanitized query)
        session.rag_service.create_query_embedding(sanitized_query)

        # retrive relevant docs 
        session.rag_service.retrive_documents(sanitized_query)

        # generate answer
        answer = session.rag_service.answer_query(sanitized_query)
        sources = []
        if hasattr(session.rag_service, 'result') and session.rag_service.result:
            matches = session.rag_service.result
            for match in matches[:3]:  # Top 3 sources
                metadata = match.metadata
                score = session.rag_service.metadataservice.cosine_similarity(vec1=session.rag_service.embedding_model.embed_query(match.page_content), vec2=session.rag_service.embedding_model.embed_query(
                    session.rag_service.query
                ))
                sources.append(SourceDocument(
                            doc_id=metadata['doc_id'],
                            page=metadata['page_no'],
                            text=match.page_content,
                            score=score,
                            metadata=metadata
                        ))
        return QueryResponse(
            session_id=session_id,
            query=sanitized_query,
            answer=answer,
            message="Query processed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error processing query for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing query")

@router.get("/session/{session_id}/status")
async def get_session_status(
    session_id: str,
    session: Session = Depends(get_session)
):
    """Get session status and information"""
    return {
        "session_id": session_id,
        "created_at": session.created_at,
        "last_activity": session.last_activity,
        "document_uploaded": session.document_uploaded,
        "vector_store_created": session.vector_store_created,
        "document_info": session.document_info
    }

    
    

