from typing import Optional, List
from pydantic import BaseModel

class FollowUpQA(BaseModel):
    question: str
    answer: Optional[str] = None

class QA(BaseModel):
    question: str
    answer: Optional[str] = None
    follow_ups: Optional[List[FollowUpQA]] = None
    feedback: Optional[str] = None

class InterviewSession(BaseModel):
    interview_id: str
    member_interview_id: str
    session_id: str
    video_path: Optional[str] = None
    qa_flow: List[QA]
    final_report: Optional[str] = None
