from interview.domain.interview import InterviewSession, Cursor
from interview.domain.repository.interview_repo import InterviewRepository
from interview.domain.llm.llm_client import LLMClient
from interview.domain.tts.tts_client import TTSClient
from typing import List
import uuid

MAX_QUESTIONS = 5
MAX_FOLLOW_UPS = 2

class InterviewService:
    def __init__(self, repo: InterviewRepository, llm: LLMClient, tts: TTSClient):
        self.repo = repo
        self.llm = llm
        self.tts = tts

    def create_session_with_questions(self, interview_id, member_interview_id, info: dict) -> InterviewSession:
        question_text = self.llm.generate_questions(info)
        questions = [q.strip() for q in question_text.split("\n") if q.strip()][:MAX_QUESTIONS]

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        qa_flow = []

        for i, q in enumerate(questions):
            filename = f"{session_id}_{i}.mp3"
            try:
                s3_uri = self.tts.synthesize_to_s3(q, filename=filename)
            except Exception as e:
                s3_uri = None

            qa_flow.append({
                "question": q,
                "audio_path": s3_uri,
                "answer": None,
                "feedback": None,
                "follow_ups": [],
                "follow_up_length": 0,
            })

        session = InterviewSession(
            interview_id=interview_id,
            member_interview_id=member_interview_id,
            session_id=session_id,
            cursor=Cursor(0, -1),
            video_path=None,
            qa_flow=qa_flow,
            question_length=len(questions),
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
        enriched_follow_ups = []

        for i, question in enumerate(follow_ups[:MAX_FOLLOW_UPS]):
            filename = f"{session.session_id}_{index}_{i}.mp3"
            audio_path = self.tts.synthesize_to_s3(question, filename=filename)
            enriched_follow_ups.append({
                "question": question,
                "audio_path": audio_path,
                "answer": None
            })

        session.qa_flow[index].follow_up_length = len(enriched_follow_ups)
        session.qa_flow[index].follow_ups = enriched_follow_ups
        session.cursor.f_idx += 1
        self.repo.update_session(session)
        return session

    def answer_follow_up_question(self, session_id: str, index: int, f_index: int, answer: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session:
            return None
        try:
            session.qa_flow[index].follow_ups[f_index].answer = answer
            session.cursor.f_idx += 1
            self.repo.update_session(session)
            return session
        except (IndexError, KeyError):
            return None

    def generate_feedback(self, session_id: str, index: int) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session or index >= len(session.qa_flow):
            return None
        feedback = self.llm.generate_feedback(session, index)
        session.qa_flow[index].feedback = feedback
        session.cursor.q_idx += 1
        session.cursor.f_idx = -1
        self.repo.update_session(session)
        return session

    def generate_final_report(self, session_id: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session:
            return None
        final_report = self.llm.generate_final_report(session)
        session.final_report = final_report
        self.repo.update_session(session)
        return session

    def get_all_sessions(self) -> List[InterviewSession]:
        return self.repo.get_all_sessions()

    def get_session_by_id(self, session_id: str) -> InterviewSession:
        return self.repo.get_session_by_id(session_id)

    def get_session_by_interview_and_member_interview_id(self, interview_id: str, member_interview_id: str) -> InterviewSession:
        return self.repo.get_session_by_interview_and_member_interview_id(interview_id, member_interview_id)

    def delete_session(self, session_id: str) -> bool:
        return self.repo.delete_session(session_id)

    def delete_all_sessions(self) -> int:
        return self.repo.delete_all_sessions()
