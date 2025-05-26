from fastapi import APIRouter, HTTPException
from typing import List
import json

from interview.domain.interview import InterviewSession, FollowUpQA
from interview.application.interview_service import InterviewService
from interview.infra.repository.interview_repo import InterviewRepositoryDynamo
from interview.infra.llm.llm_factory import LLMClientFactory

router = APIRouter(prefix="/interview")
repo = InterviewRepositoryDynamo()
llm = LLMClientFactory.get_llm_client()
service = InterviewService(repo, llm)

@router.post("/{interview_id}/{member_interview_id}/generate_questions", response_model=InterviewSession)
def generate_questions(interview_id: str, member_interview_id: str):
    with open("info.json", "r") as f:
        info = json.load(f)
    session = service.create_session_with_questions(interview_id, member_interview_id, info)
    return session

@router.patch("/session/{session_id}/qa/{index}/answer")
def answer_main_question(session_id: str, index: int, answer: str):
    session = service.answer_main_question(session_id, index, answer)
    if not session:
        raise HTTPException(status_code=404, detail="Session or question not found")
    return session

@router.post("/session/{session_id}/qa/{index}/generate_follow-ups", response_model=InterviewSession)
def generate_follow_up_questions(session_id: str, index: int):
    session = service.generate_follow_up_questions(session_id, index)
    if not session:
        raise HTTPException(status_code=404, detail="Session or question not found")
    return session

@router.patch("/session/{session_id}/qa/{index}/follow-up/{f_index}/answer")
def answer_follow_up_question(session_id: str, index: int, f_index: int, answer: str):
    session = service.answer_follow_up_question(session_id, index, f_index, answer)
    if not session:
        raise HTTPException(status_code=404, detail="Follow-up question not found")
    return session

@router.post("/session/{session_id}/qa/{index}/feedback", response_model=InterviewSession)
def generate_feedback(session_id: str, index: int):
    return service.generate_feedback(session_id, index)

@router.post("/session/{session_id}/report", response_model=InterviewSession)
def generate_final_report(session_id: str):
    return service.generate_final_report(session_id)

@router.get("/sessions", response_model=List[InterviewSession])
def list_all_sessions():
    return service.get_all_sessions()

@router.get("/session/{session_id}", response_model=InterviewSession)
def get_session_by_id(session_id: str):
    session = service.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/session/{interview_id}/{member_interview_id}", response_model=InterviewSession)
def get_session_by_interview_and_member_interview_id(interview_id: str, member_interview_id: str):
    return service.get_session_by_interview_and_member_interview_id(interview_id, member_interview_id)

@router.delete("/session/{session_id}")
def delete_session(session_id: str):
    deleted = service.delete_session(session_id)
    if deleted:
        return {"message": f"Session {session_id} deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@router.delete("/sessions")
def delete_all_sessions():
    count = service.delete_all_sessions()
    return {"message": f"{count} session(s) deleted"}