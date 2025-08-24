# interview_service.py (수정 완료)

from interview.domain.interview import InterviewSession, Cursor
from interview.domain.repository.interview_repo import InterviewRepository
from interview.domain.llm.llm_client import LLMClient
from interview.domain.tts.tts_client import TTSClient
from interview.domain.ocr.ocr_client import OCRClient
from interview.domain.info import InfoModel
from typing import List
import uuid
import httpx
import logging
import asyncio
import copy

# NOTE: 이 값은 API 요청에 questionNumber가 없을 경우의 기본값으로 계속 사용됩니다.
MAX_QUESTIONS = 5
MAX_FOLLOW_UPS = 2

class InterviewService:
    def __init__(self, repo: InterviewRepository, llm: LLMClient, tts: TTSClient, ocr: OCRClient):
        self.repo = repo
        self.llm = llm
        self.tts = tts

    async def create_sessions_concurrently(self, info: InfoModel) -> List[InterviewSession]:
        base_dict = info.model_dump()
        interview_id = None
        # NOTE: 컨트롤러에서 이미 검증했지만, 서비스 계층에서도 안전하게 id를 다시 확인합니다.
        if info.result:
            interview_id = str(info.result.interviewId or getattr(info.result.interview, 'interviewId', None))

        async def create_for_participant(participant):
            member_interview_id = str(participant.memberInterviewId)
            info_one = copy.deepcopy(base_dict)
            info_one["result"]["participants"] = [participant.model_dump()]
            return await asyncio.to_thread(
                self.create_session_with_questions,
                interview_id,
                member_interview_id,
                info_one
            )

        sessions = await asyncio.gather(*(create_for_participant(p) for p in info.result.participants))
        return sessions

    def create_session_with_questions(self, interview_id: str, member_interview_id: str, info: dict) -> InterviewSession:
        if not all([interview_id, member_interview_id, info]):
            raise ValueError("interview_id, member_interview_id, and info must be provided")

        participant_info = info["result"]["participants"][0]
        cover_letter = participant_info.get("coverLetterDTO", {}).get("qnaList", [])
        resume_url = participant_info.get("resumeDTO", {}).get("fileUrl")

        # CHANGED: info에서 questionNumber 값을 추출하고, 없으면 기본값(MAX_QUESTIONS) 사용
        try:
            # 안전한 접근을 위해 .get()을 연쇄적으로 사용합니다.
            question_count = info.get("result", {}).get("options", {}).get("questionNumber") or MAX_QUESTIONS
        except (AttributeError, TypeError):
            question_count = MAX_QUESTIONS

        question_text = self.llm.generate_questions(info, cover_letter)
        # CHANGED: 하드코딩된 MAX_QUESTIONS 대신 추출한 question_count 사용
        questions = [q.strip() for q in question_text.split("\n") if q.strip()][:question_count]
        
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        qa_flow = []

        for i, q in enumerate(questions):
            filename = f"{session_id}_{i}.mp3"
            s3_uri = None
            try:
                s3_uri = self.tts.synthesize_to_s3(q, filename=filename)
            except Exception as e:
                logging.error(f"TTS generation failed for question '{q}': {e}")

            qa_flow.append({
                "question": q, "audio_path": s3_uri, "answer": None,
                "feedback": None, "follow_ups": [], "follow_up_length": 0,
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
        logging.info(f"Session {session_id} created for member {member_interview_id} with {len(questions)} questions.")
        return session

    # --- 이하 메서드는 변경 사항 없습니다 ---

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
            enriched_follow_ups.append({"question": question, "audio_path": audio_path, "answer": None})

        session.qa_flow[index].follow_up_length = len(enriched_follow_ups)
        session.qa_flow[index].follow_ups = enriched_follow_ups
        session.cursor.f_idx = 0
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
            
            if session.cursor.f_idx >= session.qa_flow[index].follow_up_length:
                self.generate_feedback(session_id, index)
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

        if session.cursor.q_idx >= session.question_length:
            self.generate_final_report(session_id)
        return session

    def generate_final_report(self, session_id: str) -> InterviewSession:
        session = self.repo.get_session_by_id(session_id)
        if not session:
            return None
        final_report = self.llm.generate_final_report(session)
        session.final_report = final_report
        self.repo.update_session(session)

        try:
            post_payload = {
                "interviewId": session.interview_id,
                "memberInterviewId": session.member_interview_id
            }
            response = httpx.post(
                "https://interview.play-qr.site/notifications/feedback",
                json=post_payload,
                timeout=5.0
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"❌ Failed to send report to external server: {e}")

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