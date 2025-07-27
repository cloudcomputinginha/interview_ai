import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv
load_dotenv()
from interview.interface.controllers import interview_controller
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

app = FastAPI()
container = InterviewContainer()
container.wire(modules=["interview.interface.controllers"])
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
