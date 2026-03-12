from typing import Optional, List, Tuple
from dataclasses import dataclass
from pydantic import BaseModel
from interview.domain.info import InfoModel

@dataclass
class Cursor:
    q_idx: int
    f_idx: int

class FollowUpQA(BaseModel):
    question: str
    audio_path: str
    answer: Optional[str] = None

class QA(BaseModel):
    question: str
    audio_path: str
    answer: Optional[str] = None
    follow_up_length: int
    follow_ups: Optional[List[FollowUpQA]] = None
    feedback: Optional[str] = None

class InterviewSession(BaseModel):
    interview_id: str
    member_interview_id: str
    session_id: str
    cursor: Cursor
    video_path: Optional[str] = None
    question_length: int
    # info: InfoModel
    qa_flow: List[QA]
    final_report: Optional[str] = None
