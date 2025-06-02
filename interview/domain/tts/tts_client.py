from abc import ABC, abstractmethod
from typing import List

class PollyClient(ABC):
    @abstractmethod
    def synthesize_to_s3(self, text: str, voice_id: str, filename: str) -> str: ...
