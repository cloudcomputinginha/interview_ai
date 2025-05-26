from interview.domain.repository.interview_repo import InterviewRepository
from interview.domain.interview import InterviewSession
import boto3
import os
from boto3.dynamodb.conditions import Key

class InterviewRepositoryDynamo(InterviewRepository):
    def __init__(self):
        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        self.table = self.dynamodb.Table(os.getenv("DYNAMO_TABLE_NAME", "inha-pj-08-ai-dynamo"))

    def save_session(self, session: InterviewSession):
        self.table.put_item(Item=session.dict())

    def update_session(self, session: InterviewSession):
        self.save_session(session)  # DynamoDB는 put_item으로 upsert 가능

    def get_all_sessions(self):
        response = self.table.scan()
        return [InterviewSession(**item) for item in response.get("Items", [])]

    def get_session_by_interview_and_member_interview_id(self, interview_id: str, member_interview_id: str):
        response = self.table.query(
            KeyConditionExpression=Key("interview_id").eq(interview_id) & Key("member_interview_id").eq(member_interview_id)
        )
        items = response.get("Items", [])
        return InterviewSession(**items[0]) if items else None

    def get_session_by_id(self, session_id: str):
        response = self.table.scan(
            FilterExpression=Key("session_id").eq(session_id)
        )
        items = response.get("Items", [])
        return InterviewSession(**items[0]) if items else None

    def delete_session(self, session_id: str) -> bool:
        session = self.get_session_by_id(session_id)
        if not session:
            return False
        self.table.delete_item(
            Key={
                "interview_id": session.interview_id,
                "member_interview_id": session.member_interview_id
            }
        )
        return True

    def delete_all_sessions(self) -> int:
        response = self.table.scan()
        deleted = 0
        for item in response.get("Items", []):
            self.table.delete_item(
                Key={
                    "interview_id": item["interview_id"],
                    "member_interview_id": item["member_interview_id"]
                }
            )
            deleted += 1
        return deleted
