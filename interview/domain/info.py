from pydantic import BaseModel
from typing import List, Literal, Optional
from datetime import datetime

class QnA(BaseModel):
    question: str
    answer: str

class CoverLetterDTO(BaseModel):
    coverletterId: int
    corporateName: str
    jobName: str
    qnaList: List[QnA]
    createdAt: datetime

class ResumeDTO(BaseModel):
    resumeId: int
    fileUrl: str

class Participant(BaseModel):
    memberInterviewId: int
    resumeDTO: ResumeDTO
    coverLetterDTO: CoverLetterDTO

class Interview(BaseModel):
    interviewId: int
    corporateName: str
    jobName: str
    startType: str
    participantCount: int

class Options(BaseModel):
    interviewFormat: str
    interviewType: str
    voiceType: str
    questionNumber: int
    answerTime: int

class Result(BaseModel):
    interviewId: int
    interview: Interview
    options: Options
    participants: List[Participant]

class InfoModel(BaseModel):
    isSuccess: bool
    code: str
    message: str
    result: Result
