from containers import InterviewContainer
from interview.application.interview_service import InterviewService

# Dependency Injector 컨테이너 인스턴스 생성
container = InterviewContainer()

def get_interview_service() -> InterviewService:
    return container.service()
