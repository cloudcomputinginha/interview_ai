from abc import ABC, abstractmethod
from typing import List

class LLMClient(ABC):
    @abstractmethod
    def generate_questions(self, info: dict) -> str: ...

    @abstractmethod
    def generate_follow_up(self, qa_history: list[dict]) -> str: ...
        
    @abstractmethod
    def generate_feedback(self, qa_history: list[dict]) -> str: ...

    @abstractmethod
    def generate_final_report(self, qa_history: list[dict]) -> str: ...