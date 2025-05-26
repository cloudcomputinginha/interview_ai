from abc import ABC, abstractmethod
from typing import List
from interview.domain.interview import InterviewSession

class InterviewRepository(ABC):
    @abstractmethod
    def __init__(self): ...

    @abstractmethod
    def save_session(self, session: InterviewSession):
        self.collection.insert_one(session.dict())

    @abstractmethod
    def update_session(self, session: InterviewSession): ...

    @abstractmethod
    def get_all_sessions(self): ...

    @abstractmethod
    def get_session_by_interview_and_member_interview_id(self, interview_id, member_interview_id: str): ...

    @abstractmethod
    def get_session_by_id(self, session_id: str): ...

    @abstractmethod
    def delete_session(self, session_id: str) -> bool: ...

    @abstractmethod
    def delete_all_sessions(self) -> int: ...