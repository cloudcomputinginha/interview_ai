# interview_controller.py (수정 완료)

from fastapi import APIRouter, HTTPException, Depends
from fastapi.requests import Request
from typing import List
import fitz
import requests
import tempfile
import pymupdf4llm
import logging # 로깅을 위해 추가

from interview.domain.interview import InterviewSession
from interview.domain.info import InfoModel
from interview.application.interview_service import InterviewService
from interview.interface.dependencies import get_interview_service

router = APIRouter(prefix="/interview")

@router.post("/generate_questions", response_model=List[InterviewSession])
async def generate_questions(
    info: InfoModel,
    service: InterviewService = Depends(get_interview_service)
):
    # --- 기본 검증 (유지) ---
    if not info or not info.result or not info.result.participants:
        raise HTTPException(status_code=400, detail="Required data is missing.")
    
    # CORRECTED: interviewId를 찾는 기존 검증 로직으로 복원
    result = info.result
    interview_id = getattr(result, "interviewId", None)
    if interview_id is None and getattr(result, "interview", None):
        interview_id = getattr(result.interview, "interviewId", None)
    
    if interview_id is None:
        raise HTTPException(status_code=400, detail="interviewId is missing.")

    # REFACTOR: 복잡했던 병렬 처리 로직을 서비스 호출 한 줄로 대체
    try:
        # NOTE: 서비스 계층은 이미 Pydantic 모델을 받도록 수정되었으므로 그대로 info를 전달합니다.
        sessions = await service.create_sessions_concurrently(info)
        return sessions
    except Exception as e:
        # 서비스 계층에서 발생한 에러 처리
        logging.error(f"Error during concurrent session creation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create interview sessions.")

# --- 이하 엔드포인트는 변경 사항 없습니다 ---

@router.patch("/session/{session_id}/qa/{index}/answer")
async def answer_main_question(
    session_id: str,
    index: int,
    request: Request,
    service: InterviewService = Depends(get_interview_service)
    ):
    answer = (await request.body()).decode("utf-8")
    session = service.answer_main_question(session_id, index, answer)
    if not session:
        raise HTTPException(status_code=404, detail="Session or question not found")
    return session

@router.post("/session/{session_id}/qa/{index}/generate_follow-ups", response_model=InterviewSession)
def generate_follow_up_questions(
    session_id: str, 
    index: int,
    service: InterviewService = Depends(get_interview_service)
    ):
    session = service.generate_follow_up_questions(session_id, index)
    if not session:
        raise HTTPException(status_code=404, detail="Session or question not found")
    return session

@router.patch("/session/{session_id}/qa/{index}/follow-up/{f_index}/answer")
async def answer_follow_up_question(
    session_id: str,
    index: int,
    f_index: int,
    request: Request,
    service: InterviewService = Depends(get_interview_service)
    ):
    answer = (await request.body()).decode("utf-8")
    session = service.answer_follow_up_question(session_id, index, f_index, answer)
    if not session:
        raise HTTPException(status_code=404, detail="Follow-up question not found")
    return session

@router.get("/ocr")
def do_ocr(pdf_path:str):
    response = requests.get(pdf_path)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name
    
    doc = fitz.open(tmp_path)
    md_text = pymupdf4llm.to_markdown(doc, write_images=False)
    
    return md_text

@router.get("/sessions", response_model=List[InterviewSession])
def list_all_sessions(service: InterviewService = Depends(get_interview_service)):
    return service.get_all_sessions()

@router.get("/session/{session_id}", response_model=InterviewSession)
def get_session_by_id(
    session_id: str,
    service: InterviewService = Depends(get_interview_service)
    ):
    session = service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/session/{interview_id}/{member_interview_id}", response_model=InterviewSession)
def get_session_by_interview_and_member_interview_id(
    interview_id: str, 
    member_interview_id: str,
    service: InterviewService = Depends(get_interview_service)
    ):
    session = service.get_session_by_interview_and_member_interview_id(interview_id, member_interview_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    service: InterviewService = Depends(get_interview_service)
    ):
    if service.delete_session(session_id):
        return {"message": f"Session {session_id} deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@router.delete("/sessions")
def delete_all_sessions(service: InterviewService = Depends(get_interview_service)):
    count = service.delete_all_sessions()
    return {"message": f"{count} session(s) deleted"}