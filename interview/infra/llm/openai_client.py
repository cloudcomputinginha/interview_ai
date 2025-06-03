import os
from interview.domain.interview import InterviewSession
from interview.domain.llm.llm_client import LLMClient
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

class GPTClient(LLMClient):
    def __init__(self):
        self.use_llm = os.getenv("USE_LLM", "false").lower() == "true"
        self.llm = ChatOpenAI(
            model_name="gpt-4",  # 또는 "gpt-3.5-turbo"
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    def generate_questions(self, info: dict) -> str:
        prompt = f"""
너는 면접관이야. 다음 지원자 정보를 바탕으로 본질적인 면접 질문을 5개 이하로 작성해줘. 숫자와 함께 줄바꿈된 형식으로.

이름: {info['name']}
나이: {info['age']}
학력: {info['education']}
지원 회사: {info['company']}
지원 직무: {info['position']}
"""
        if not self.use_llm:
            return """1. 자기소개\n2. 지원동기\n3. 장점과 단점\n4. 직무 관련 경험\n5. 향후 커리어 목표"""
        else:
            messages = [
                SystemMessage(content="너는 면접 질문을 생성하는 면접관이야."),
                HumanMessage(content=prompt)
            ]
            
            try:
                response = self.llm(messages)
                return response.content
            except Exception as e:
                print(f"Error generating questions: {e}")
                return None

    def generate_follow_up(self, session: InterviewSession, index: int) -> list:
        if not self.use_llm:
            return [
                "이 경험이 본인의 성장에 어떤 영향을 주었나요?",
                "그 상황에서 다른 선택을 했다면 결과가 달라졌을까요?"
            ]

        messages = [SystemMessage(content="너는 인공지능 면접관이야.")]
        for qa in session.qa_flow:
            messages.append(HumanMessage(content=f"질문: {qa.question}\n답변: {qa.answer or '없음'}"))
            for fqa in qa.follow_ups:
                messages.append(HumanMessage(content=f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}"))

        messages.append(HumanMessage(content=f"위 대화를 참고해서 '{session.qa_flow[index].question}'에 대한 꼬리 질문 2개를 작성해줘."))

        try:
            response = self.llm(messages)
            return [line.strip() for line in response.content.split("\n") if line.strip()]
        except Exception as e:
            print(f"Error generating follow-up questions: {e}")
            return None

    def generate_feedback(self, session: InterviewSession, index: int) -> str:
        if not self.use_llm:
            return "논리적으로 잘 설명했으나, 구체적인 사례가 부족합니다."

        messages = [SystemMessage(content="너는 인공지능 면접관이야.")]
        qa = session.qa_flow[index]

        messages.append(HumanMessage(content=f"질문: {qa.question}\n답변: {qa.answer or '없음'}"))
        for fqa in qa.follow_ups:
            messages.append(HumanMessage(content=f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}"))

        messages.append(HumanMessage(content="위 응답에 대한 면접 피드백을 1~2문장으로 제공해줘."))

        try:
            response = self.llm(messages)
            return response.content
        except Exception as e:
            print(f"Error generating feedback: {e}")
            return None

    def generate_final_report(self, session: InterviewSession) -> str:
        if not self.use_llm:
            return "지원자는 문제 해결 능력과 협업 역량이 뛰어나며, 직무 적합성이 높습니다."

        messages = [SystemMessage(content="너는 면접 평가자야.")]
        for qa in session.qa_flow:
            messages.append(HumanMessage(content=f"질문: {qa.question}\n답변: {qa.answer or '없음'}"))
            for fqa in qa.follow_ups:
                messages.append(HumanMessage(content=f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}"))

        messages.append(HumanMessage(content="전체 면접 내용을 바탕으로 종합 평가를 작성해줘."))

        try:
            response = self.llm(messages)
            return response.content
        except Exception as e:
            print(f"Error generating final report: {e}")
            return None