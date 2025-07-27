from dependency_injector import containers, providers
from interview.application.interview_service import InterviewService
from interview.domain.repository.interview_repo import InterviewRepository
from interview.infra.repository.interview_repo_mongo import InterviewRepositoryMongo
from interview.infra.repository.interview_repo_dynamo import InterviewRepositoryDynamo
from interview.infra.llm.openai_client import GPTClient
from interview.infra.llm.bedrock_client import BedrockClient
from interview.infra.llm.openchat_client import OpenChatClient
from interview.infra.tts.polly_client import PollyClient
from interview.infra.ocr.tesseract_client import TesseractOCRClient
import os

class InterviewRepositoryFactory:
    @staticmethod
    def get_repository() -> InterviewRepository:
        backend = os.getenv("REPO_BACKEND", "dynamo").lower()
        if backend == "mongo":
            return InterviewRepositoryMongo()
        elif backend == "dynamo":
            return InterviewRepositoryDynamo()
        else:
            raise ValueError(f"Unsupported REPO_BACKEND: {backend}")

class LLMClientFactory:
    @staticmethod
    def get_llm_client():
        provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

        if provider == "bedrock":
            return BedrockClient()
        elif provider == "openai":
            return GPTClient()
        elif provider == "openchat":
            return OpenChatClient()
        else:
            raise ValueError(f"Unsupported LLM_CLIENT: {provider}")

class TTSClientFactory:
    @staticmethod
    def get_tts_client():
        provider = os.getenv("TTS_PROVIDER", "polly").lower()

        if provider == "polly":
            return PollyClient()
        else:
            raise ValueError(f"Unsupported TTS_CLIENT: {provider}")

class OCRClientFactory:
    @staticmethod
    def get_ocr_client():
        provider = os.getenv("OCR_PROVIDER", "tesseract").lower()

        if provider == "tesseract":
            return TesseractOCRClient()
        else:
            raise ValueError(f"Unsupported OCR_CLIENT: {provider}")


class InterviewContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["interview.interface.controllers"]
    )

    repo = providers.Singleton(InterviewRepositoryFactory.get_repository)
    llm = providers.Singleton(LLMClientFactory.get_llm_client)
    tts = providers.Singleton(TTSClientFactory.get_tts_client)
    ocr = providers.Singleton(OCRClientFactory.get_ocr_client)
    service = providers.Factory(InterviewService, repo=repo, llm=llm, tts=tts, ocr=ocr)
