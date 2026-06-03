from fastapi import APIRouter, Depends

from app.agents.document_editor.service import edit_document
from app.agents.document_editor.schemas import DocumentEditInput, DocumentEditOutput
from app.dependencies.auth import current_user

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/document-editor/run", response_model=DocumentEditOutput)
def run_document_editor(payload: DocumentEditInput, _actor=Depends(current_user)) -> DocumentEditOutput:
    return edit_document(payload)
