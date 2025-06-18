import os
import requests
from interview.domain.interview import InterviewSession
from interview.domain.llm.llm_client import LLMClient
from langchain.schema import SystemMessage, HumanMessage


class OpenChatClient(LLMClient):
    def __init__(self):
        self.use_llm = os.getenv("USE_LLM", "false").lower() == "true"
        self.api_url = os.getenv("OPENCHAT_API_URL", "http://gpu-server-ip:8000/generate")

    def _invoke(self, messages: list) -> str:
        if not self.use_llm:
            return None

        # OpenChat 스타일 prompt 구성
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt += f"### System:\n{msg.content.strip()}\n"
            elif isinstance(msg, HumanMessage):
                user_prompt += f"### User:\n{msg.content.strip()}\n"

        prompt = f"{system_prompt}{user_prompt}### Assistant:"

        try:
            res = requests.post(self.api_url, json={
                "prompt": prompt,
                "temperature": 0.7,
                "max_new_tokens": 512
            })
            res.raise_for_status()

            # 💡 응답이 JSON 문자열인지, 그냥 문자열인지 구분
            try:
                data = res.json()
                if isinstance(data, dict):
                    return data.get("response", "")
                elif isinstance(data, str):
                    return data  # 혹시 string 자체가 리턴되는 경우
                else:
                    return ""
            except Exception:
                return res.text  # fallback 처리

        except Exception as e:
            print(f"❌ Error invoking OpenChat API: {e}")
            return ""

    def generate_questions(self, info: dict) -> str:
        if not self.use_llm:
            return "1. 자기소개\n2. 지원동기\n3. 장점과 단점\n4. 직무 관련 경험\n5. 향후 커리어 목표"

        prompt = f"""
        너는 면접관이야. 다음은 지원자 정보야.

        이름: {info['name']}
        나이: {info['age']}
        학력: {info['education']}
        지원 회사: {info['company']}
        지원 직무: {info['position']}

        이 정보를 바탕으로 본질적인 면접 질문을 5개 작성해줘.
        네가 생성한 질문 문자열을 line 별로 split하는 규칙 기반 알고리즘 수행 예정이야.
        그러니 면접 질문만 줄바꿈을 통해 답변해주고, "예, 알겠습니다"와 같은 답변은 절대 포함시키지 마.
        다시 한번 말할게. 오로지 질문만 줄바꿈을 통해 5개 생성해.
        """

        messages = [
            SystemMessage(content="너는 면접 질문을 생성하는 면접관이야."),
            HumanMessage(content=prompt)
        ]

        return self._invoke(messages)

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

        messages.append(
            HumanMessage(
                content=f"""위 대화를 참고해서 '{session.qa_flow[index].question}'에 대한 꼬리 질문 2개를 작성해줘.
                네가 생성한 꼬리 질문 문자열을 line 별로 split하는 규칙 기반 알고리즘 수행 예정이야.
                그러니 꼬리 질문만 줄바꿈을 통해 답변해주고, "예, 알겠습니다"와 같은 답변은 절대 포함시키지 마.
                기존 질문과 같은 내용을 꼬리 질문으로 생성하지 마"""
            )
        )

        try:
            response = self._invoke(messages)
            return [line.strip() for line in response.split("\n") if line.strip()]
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
        messages.append(HumanMessage(content="""위 응답에 대한 면접 피드백을 제공해줘. 
                                            네가 생성한 피드백을 클라이언트에게 제공하는 규칙 기반 알고리즘 수행 예정이야.
                                            그러니 피드백 내용만 답변해주고, "예, 알겠습니다"와 같은 답변은 절대 포함시키지 마."""))

        return self._invoke(messages)

    def generate_final_report(self, session: InterviewSession) -> str:
        if not self.use_llm:
            return "지원자는 문제 해결 능력과 협업 역량이 뛰어나며, 직무 적합성이 높습니다."

        messages = [SystemMessage(content="너는 면접 평가자야.")]
        for qa in session.qa_flow:
            messages.append(HumanMessage(content=f"질문: {qa.question}\n답변: {qa.answer or '없음'}"))
            for fqa in qa.follow_ups:
                messages.append(HumanMessage(content=f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}"))
        messages.append(HumanMessage(content="""위 면접에 대한 종합 평가를 제공해줘. 
                                            네가 생성한 종합 평가를 클라이언트에게 제공하는 규칙 기반 알고리즘 수행 예정이야.
                                            그러니 종합 평가 내용만 답변해주고, "예, 알겠습니다"와 같은 답변은 절대 포함시키지 마."""))

        return self._invoke(messages)
