from interview.domain.repository.interview_repo import InterviewRepository
from interview.domain.interview import InterviewSession
from pymongo import MongoClient
import os

class InterviewRepositoryMongo(InterviewRepository):
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        client = MongoClient(mongo_uri)
        self.collection = client["interview_db"]["sessions"]

    def save_session(self, session: InterviewSession):
        self.collection.insert_one(session.dict())

    def update_session(self, session: InterviewSession):
        self.collection.replace_one(
            {"session_id": session.session_id}, session.dict(), upsert=True
        )

    def get_all_sessions(self):
        return [InterviewSession(**doc) for doc in self.collection.find()]

    def get_session_by_interview_and_member_interview_id(self, interview_id: str, member_interview_id: str):
        doc = self.collection.find_one({
            "interview_id": interview_id,
            "member_interview_id": member_interview_id
        })
        return InterviewSession(**doc) if doc else None

    def get_session_by_id(self, session_id: str):
        doc = self.collection.find_one({"session_id": session_id})
        return InterviewSession(**doc) if doc else None

    def delete_session(self, session_id: str) -> bool:
        result = self.collection.delete_one({"session_id": session_id})
        return result.deleted_count > 0

    def delete_all_sessions(self) -> int:
        result = self.collection.delete_many({})
        return result.deleted_count
