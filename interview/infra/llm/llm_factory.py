import os

from interview.infra.llm.openai_client import GPTClient
from interview.infra.llm.bedrock_client import BedrockClient

class LLMClientFactory:
    @staticmethod
    def get_llm_client():
        provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

        if provider == "bedrock":
            return BedrockClient()
        else:
            return GPTClient()
