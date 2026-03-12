import os
import requests
from interview.domain.interview import InterviewSession
from interview.domain.llm.llm_client import LLMClient
from langchain.schema import SystemMessage, HumanMessage


class LocalClient(LLMClient):
    """vLLM FastAPI 서버(/llm/generate) 호출용 클라이언트"""

    def __init__(self):
        self.use_llm = os.getenv("USE_LLM", "false").lower() == "true"
        # FastAPI 서버 URL 반드시 /llm/generate
        self.api_url = os.getenv("GPU_API_URL", "http://gpu-server-ip:8000/llm/generate")

    # ─────────────────── 내부 헬퍼 ────────────────────
    @staticmethod
    def _to_prompt(messages: list[str]) -> str:
        """
        메시지 문자열 리스트를 vLLM 프롬프트 형식(<|begin_of_text|> …)으로 결합
        순서는 이미 사용자가 보장해야 함.
        """
        headered = []
        for idx, msg in enumerate(messages):
            role = "system" if idx == 0 else "user"
            headered.append(f"<|start_header_id|>{role}<|end_header_id|>\n\n{msg}\n")
            headered.append("<|eot_id|>")
        # 마지막 assistant header
        headered.append("<|start_header_id|>assistant<|end_header_id|>")
        return "<|begin_of_text|>" + "".join(headered)

    def _post(self, prompt: str, temperature=0.7, max_new_tokens=256, top_p=0.95) -> str:
        res = requests.post(
            self.api_url,
            json={
                "prompt": prompt,
                "temperature": temperature,
                "max_new_tokens": max_new_tokens,
                "top_p": top_p,
            },
            timeout=60,
        )
        res.raise_for_status()
        return res.json().get("response", "").strip()

    # ─────────────────── 공통 호출 ────────────────────
    def _invoke(self, messages: list):
        if not self.use_llm:
            return None
        # langchain Message → str
        strs = [m.content.strip() for m in messages]
        prompt = self._to_prompt(strs)
        try:
            return self._post(prompt)
        except Exception as e:
            print(f"❌ LLM 호출 실패: {e}")
            return ""

    # ─────────────────── 기능별 메서드 ────────────────────
    def generate_questions(self, info: dict, cover_letter) -> str:
        if not self.use_llm:
            return "1. 자기소개\n2. 지원동기\n3. 장점과 단점\n4. 직무 관련 경험\n5. 향후 커리어 목표"

        sys_msg = "당신은 뛰어난 면접관입니다."
        usr_msg = (
            f"지원 회사: {info["result"]["interview"]["corporateName"]}"
            f"지원 직무: {info["result"]["options"]["questionNumber"]}"
            f"자기소개서: {cover_letter}"
            "주어진 정보를 바탕으로, 지원자에게 **본질적인 면접 질문 5개**를 작성해 주세요.\n"
            "(각 질문은 이후 꼬리 질문으로 이어집니다.)\n\n"
            "**[중요] 오직 질문 5개만 줄바꿈으로 나열하고, 그 외 코멘트는 절대 쓰지 마세요.**"
        )
        return self._invoke([SystemMessage(content=sys_msg), HumanMessage(content=usr_msg)])

    def generate_follow_up(self, session: InterviewSession, index: int) -> list[str]:
        if not self.use_llm:
            return [
                "이 경험이 본인의 성장에 어떤 영향을 주었나요?",
                "그 상황에서 다른 선택을 했다면 결과가 달라졌을까요?",
            ]

        msgs = ["너는 인공지능 면접관이야."]
        for qa in session.qa_flow:
            msgs.append(f"질문: {qa.question}\n답변: {qa.answer or '없음'}")
            for fqa in qa.follow_ups:
                msgs.append(f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}")

        msgs.append(
            f"""위 내용을 참고해 **'{session.qa_flow[index].question}'**에 대한
꼬리 질문을 두 개 작성해 줘.

- 오직 꼬리 질문 두 줄만 출력
- "예, 알겠습니다" 등 불필요 문구 금지
- 기존 질문과 중복된 내용 금지"""
        )

        resp = self._invoke([SystemMessage(content=msgs[0])] + [HumanMessage(content=m) for m in msgs[1:]])
        return [line.strip() for line in resp.split("\n") if line.strip()]

    def generate_feedback(self, session: InterviewSession, index: int) -> str:
        if not self.use_llm:
            return "논리적으로 잘 설명했으나, 구체적인 사례가 부족합니다."

        msgs = ["너는 인공지능 면접관이야."]
        qa = session.qa_flow[index]
        msgs.append(f"질문: {qa.question}\n답변: {qa.answer or '없음'}")
        for fqa in qa.follow_ups:
            msgs.append(f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}")

        msgs.append(
            "위 응답에 대한 피드백을 작성해 줘. "
            '불필요한 인삿말 없이 **피드백 내용만** 출력해.'
        )
        return self._invoke([SystemMessage(content=msgs[0])] + [HumanMessage(content=m) for m in msgs[1:]])

    def generate_final_report(self, session: InterviewSession) -> str:
        if not self.use_llm:
            return "지원자는 문제 해결 능력과 협업 역량이 뛰어나며, 직무 적합성이 높습니다."

        msgs = ["너는 면접 평가자야."]
        for qa in session.qa_flow:
            msgs.append(f"질문: {qa.question}\n답변: {qa.answer or '없음'}")
            for fqa in qa.follow_ups:
                msgs.append(f"꼬리 질문: {fqa.question}\n답변: {fqa.answer or '없음'}")

        msgs.append(
            "위 면접 내용을 종합 평가해 줘. "
            '단, 인삿말 없이 평가만 출력해.'
        )
        return self._invoke([SystemMessage(content=msgs[0])] + [HumanMessage(content=m) for m in msgs[1:]])
