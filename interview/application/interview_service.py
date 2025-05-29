from interview.domain.interview import InterviewSession
from interview.domain.repository.interview_repo import InterviewRepository
from interview.domain.llm.llm_client import LLMClient
from typing import List
import uuid

class InterviewService:
    def __init__(self, repo: InterviewRepository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    def create_session_with_questions(self, interview_id, member_interview_id, info: dict) -> InterviewSession:
        question_text = self.llm.generate_questions(info)
        questions = [q.strip() for q in question_text.split("\n") if q.strip()][:7]
        qa_flow = [{"question": q, "answer": None, "feedback": None, "follow_ups": []} for q in questions]

        session = InterviewSession(
            interview_id=interview_id,
            member_interview_id=member_interview_id,
            session_id=f"sess_{uuid.uuid4().hex[:8]}",
            video_path=None,
            qa_flow=qa_flow,
            final_report=None,
        )
        self.repo.save_session(session)
        return session

    def answer_main_question(self, session_id: str, index: int, answer: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session or index >= len(session.qa_flow):
            return None
        session.qa_flow[index].answer = answer
        self.repo.update_session(session)
        return session

    def generate_follow_up_questions(self, session_id: str, index: int) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session or index >= len(session.qa_flow):
            return None

        follow_ups = self.llm.generate_follow_up(session, index)
        session.qa_flow[index].follow_ups = [{"question": q, "answer": None} for q in follow_ups[:2]]
        self.repo.update_session(session)
        return session

    def answer_follow_up_question(self, session_id: str, index: int, f_index: int, answer: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session:
            return None
        try:
            session.qa_flow[index].follow_ups[f_index].answer = answer
            self.repo.update_session(session)
            return session
        except (IndexError, KeyError):
            return None

    def generate_feedback(self, session_id: str, index: int) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        feedback = self.llm.generate_feedback(session, index)
        session.qa_flow[index].feedback = feedback
        self.repo.update_session(session)
        return session

    def generate_final_report(self, session_id: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        final_report = self.llm.generate_final_report(session)
        session.final_report = final_report
        self.repo.update_session(session)
        return session

    def get_all_sessions(self) -> List[InterviewSession]:
        return self.repo.get_all_sessions()

    def get_session_by_id(self, session_id: str) -> InterviewSession:
        return self.repo.get_session_by_id(session_id)

    def get_session_by_interview_and_member_interview_id(self, interview_id: str, member_interview_id: str) -> List[InterviewSession]:
        return self.repo.get_session_by_interview_and_member_interview_id(interview_id, member_interview_id)

    def delete_session(self, session_id: str) -> bool:
        return self.repo.delete_session(session_id)

    def delete_all_sessions(self) -> int:
        return self.repo.delete_all_sessions()
