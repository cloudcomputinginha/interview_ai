# main.py

import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()

# REFACTOR: 컨테이너와 와이어링(wiring)을 먼저 처리하기 위해 컨트롤러 import를 아래로 이동합니다.
from containers import InterviewContainer
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from datetime import datetime, timedelta

class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        kst = datetime.utcfromtimestamp(record.created) + timedelta(hours=9)
        return kst.strftime(datefmt or "%Y-%m-%d %H:%M:%S")

handler = logging.StreamHandler()
handler.setFormatter(KSTFormatter("[%(asctime)s] %(levelname)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = [handler]


# --- 의존성 주입 설정 (컨트롤러 import 전) ---
app = FastAPI()
container = InterviewContainer()
# NOTE: 컨트롤러의 의존성을 해결할 준비를 먼저 합니다.
container.wire(modules=["interview.interface.controllers.interview_controller"])

# --- 컨트롤러 import (의존성 주입 준비 후) ---
from interview.interface.controllers import interview_controller
app.include_router(interview_controller.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def hello():
    return {"Hello" : "World"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None, reload_excludes=["../output.log"])