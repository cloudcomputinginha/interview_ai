# interview/interface/dto.py (새 파일 또는 기존 InfoModel이 있는 파일에 추가)

from pydantic import BaseModel, Field
from typing import List
from interview.domain.info import InfoModel # 기존 InfoModel import

# --- 요청(Request) 모델 ---

class AnswerRequest(BaseModel):
    """답변 제출 시 사용할 모델"""
    answer: str = Field(..., min_length=1, description="사용자의 답변 텍스트")


# --- 응답(Response) 모델 ---

class SessionIdentifier(BaseModel):
    """생성된 세션의 식별자 정보"""
    member_interview_id: str
    session_id: str

class CreateSessionsResponse(BaseModel):
    """세션 생성 API의 성공 응답 모델"""
    message: str = "Sessions created successfully."
    sessions: List[SessionIdentifier]