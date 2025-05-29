import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()  # .env 파일에서 OPENAI_API_KEY 로드
from interview.interface.controllers import interview_controller
from containers import InterviewContainer
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()
# 컨테이너 인스턴스 초기화 및 FastAPI에 연결
container = InterviewContainer()
container.wire(modules=["interview.interface.controllers"])
app.include_router(interview_controller.router)

@app.get("/")
def hello():
    return {"Hello" : "World"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)