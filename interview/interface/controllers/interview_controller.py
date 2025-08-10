from fastapi import APIRouter, Body, HTTPException, Depends
from fastapi.requests import Request
from typing import List
import json
import os
import fitz  # PyMuPDF
import requests
import tempfile
import pymupdf4llm
from interview.domain.interview import InterviewSession
from interview.domain.info import InfoModel
from interview.application.interview_service import InterviewService
from interview.interface.dependencies import get_interview_service

router = APIRouter(prefix="/interview")

@router.post("/{interview_id}/{member_interview_id}/generate_questions", response_model=InterviewSession)
def generate_questions(
    interview_id: str,
    member_interview_id: str,
    info: InfoModel,
    service: InterviewService = Depends(get_interview_service)
    ):
    # try:
    #     info_file_path = os.getenv("INFO_FILE_PATH", "info.json")
    #     with open(info_file_path, "r") as f:
    #         info = json.load(f)
    # except FileNotFoundError:
    #     raise HTTPException(status_code=500, detail="Info file not found")
    # except json.JSONDecodeError:
    #     raise HTTPException(status_code=500, detail="Invalid JSON in info file")
    if not interview_id or interview_id.strip() == "":
        raise HTTPException(status_code=400, detail="interview_id, member_interview_id, info are required")
    if not member_interview_id or member_interview_id.strip() == "":
        raise HTTPException(status_code=400, detail="interview_id, member_interview_id, info are required")
    if not info or not info.dict():
        raise HTTPException(status_code=400, detail="interview_id, member_interview_id, info are required")
        
    session = service.create_session_with_questions(interview_id, member_interview_id, info.dict())
    return session

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

# @router.post("/session/{session_id}/qa/{index}/feedback", response_model=InterviewSession)
# def generate_feedback(
#     session_id: str,
#     index: int,
#     service: InterviewService = Depends(get_interview_service)
#     ):
#     return service.generate_feedback(session_id, index)

# @router.post("/session/{session_id}/report", response_model=InterviewSession)
# def generate_final_report(
#     session_id: str,
#     service: InterviewService = Depends(get_interview_service)
#     ):
#     return service.generate_final_report(session_id)

@router.get("/ocr")
def do_ocr(pdf_path:str):
    # 1. PDF 다운로드
    response = requests.get(pdf_path)
    response.raise_for_status()  # 오류 처리

    # 2. 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name
    
    doc = fitz.open(tmp_path)
    has_text = any(page.get_text("text").strip() for page in doc)

    if not has_text:
        print("이 PDF는 텍스트 레이어가 없어 보입니다. 아래 B안(OCR)으로 진행하세요.")
    else:
        # 2) 페이지 단위로 Markdown 생성(tqdm 진행바)
        md_pages = []
        for i in range(len(doc)):
            md_i = pymupdf4llm.to_markdown(
                doc,
                pages=[i],  # 0-based page index
                write_images=False,  # 텍스트만
                ignore_images=True,  # 이미지 무시하면 텍스트 판독 더 안정
                force_text=True,  # 겹침 영역에서도 텍스트 생성
            )
            md_pages.append(f"# Page {i+1}\n\n{md_i.strip()}")

    return str(md_pages)

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
    return service.get_session_by_interview_and_member_interview_id(interview_id, member_interview_id)

@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    service: InterviewService = Depends(get_interview_service)
    ):
    deleted = service.delete_session(session_id)
    if deleted:
        return {"message": f"Session {session_id} deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@router.delete("/sessions")
def delete_all_sessions(service: InterviewService = Depends(get_interview_service)):
    count = service.delete_all_sessions()
    return {"message": f"{count} session(s) deleted"}