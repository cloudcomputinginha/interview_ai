#!/usr/bin/env python
import asyncio, json, logging
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from collections import defaultdict
from urllib.parse import urlparse, parse_qs

import websockets
from websockets.legacy.server import serve

import httpx
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
FASTAPI_BASE_URL = "https://dev-ai-api.injob.store"

# 인터뷰 파라미터(현재 하드코딩, Participants에 따라 값 직접 할당 방식으로 변경 예정)
QUESTION_COUNT = 5        # index: 0..4
FOLLOW_UP_COUNT = 2       # f_index: -1(메인), 0, 1  → 총 2개의 꼬리질문

class CustomProtocol(websockets.WebSocketServerProtocol):
    async def process_request(self, path, request_headers):
        q = parse_qs(urlparse(path).query)
        self.session_id = q.get("session_id", [None])[0]
        self.index = int(q.get("index", [0])[0])      # 단일 stt 모드 참고용
        self.f_index = int(q.get("f_index", [-1])[0]) # 단일 stt 모드 참고용
        self.participant_id = q.get("participant_id", [None])[0]
        self.mode = q.get("mode", ["stt"])[0]         # "chat" | "stt" | "team"
        return None

@dataclass
class SessionState:
    session_id: str
    sockets: Set[CustomProtocol] = field(default_factory=set)
    by_pid: Dict[str, Set[CustomProtocol]] = field(default_factory=lambda: defaultdict(set))
    order: List[str] = field(default_factory=list)           # 발언 순서
    index: int = 0                                           # 공유 index (0..QUESTION_COUNT-1)
    active_pid: Optional[str] = None

    # 참가자별 f_index 상태 (없으면 -1로 간주)
    participant_f_index: Dict[str, int] = field(default_factory=dict)

    # Transcribe
    t_client: Optional[TranscribeStreamingClient] = None
    t_stream = None
    t_handler_task: Optional[asyncio.Task] = None
    t_handler_obj: Optional["MyEventHandler"] = None

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

SESSIONS: Dict[str, SessionState] = {}
ROOMS: Dict[str, Set[CustomProtocol]] = defaultdict(set)

# ── broadcast helpers ───────────────────────────────────────────────────────

async def broadcast_json(session_id: str, obj: dict, exclude: Optional[CustomProtocol]=None):
    data = json.dumps(obj, ensure_ascii=False)
    dead = []
    for ws in list(ROOMS.get(session_id, [])):
        if ws is exclude:
            continue
        try:
            await ws.send(data)
        except websockets.ConnectionClosed:
            dead.append(ws)
    for ws in dead:
        ROOMS[session_id].discard(ws)

async def broadcast_audio(session_id: str, audio_bytes: bytes, exclude: Optional[CustomProtocol]=None):
    dead = []
    for ws in list(ROOMS.get(session_id, [])):
        if ws is exclude:
            continue
        try:
            await ws.send(audio_bytes)
        except websockets.ConnectionClosed:
            dead.append(ws)
    for ws in dead:
        ROOMS[session_id].discard(ws)

def get_f_index_for(session: SessionState, pid: Optional[str]) -> int:
    if not pid:
        return -1
    return session.participant_f_index.get(pid, -1)

async def emit_state(session: SessionState):
    await broadcast_json(session.session_id, {
        "type": "state",
        "index": session.index,
        "active_pid": session.active_pid,
        "f_index_current": get_f_index_for(session, session.active_pid),
        "order": session.order,
        "participant_f_index": session.participant_f_index,  # 전체 맵도 제공
    })

# ── Transcribe handler ──────────────────────────────────────────────────────

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, stream, session: SessionState, participant_id: str):
        super().__init__(stream)
        self.session = session
        self.participant_id = participant_id
        self.client = httpx.AsyncClient(verify=False)
        self.full_transcript = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        for result in transcript_event.transcript.results:
            if result.is_partial:
                await broadcast_json(self.session.session_id, {
                    "type": "stt_status",
                    "status": "processing",
                    "participant_id": self.participant_id,
                    "index": self.session.index,
                    "f_index": get_f_index_for(self.session, self.participant_id),
                })
                continue

            new_text = result.alternatives[0].transcript.strip()
            if not new_text:
                continue
            self.full_transcript = (self.full_transcript + " " + new_text).strip()
            f_idx = get_f_index_for(self.session, self.participant_id)

            await broadcast_json(self.session.session_id, {
                "type": "stt_text",
                "text": new_text,
                "participant_id": self.participant_id,
                "index": self.session.index,
                "f_index": f_idx,
            })
            await broadcast_json(self.session.session_id, {
                "type": "stt_status",
                "status": "end",
                "participant_id": self.participant_id,
                "index": self.session.index,
                "f_index": f_idx,
            })

            # PATCH (참가자별 f_index에 따라 분기)
            try:
                if f_idx == -1:
                    url = f"{FASTAPI_BASE_URL}/interview/session/{self.session.session_id}/qa/{self.session.index}/answer"
                else:
                    url = f"{FASTAPI_BASE_URL}/interview/session/{self.session.session_id}/qa/{self.session.index}/follow-up/{f_idx}/answer"

                resp = await self.client.patch(url, content=self.full_transcript, headers={"Content-Type": "text/plain"})
                logging.info(f"[{self.session.session_id}] ✅ PATCH {resp.status_code}: idx={self.session.index}, pid={self.participant_id}, f_index={f_idx}")
            except Exception as e:
                logging.warning(f"[{self.session.session_id}] ⚠️ PATCH 실패: {e}")

    async def close(self):
        try:
            await self.client.aclose()
        except Exception:
            pass

# ── STT control ────────────────────────────────────────────────────────────

async def start_stt_for(session: SessionState, participant_id: Optional[str]):
    if not participant_id:
        return
    await stop_stt(session)

    session.t_client = TranscribeStreamingClient(region="us-east-1")
    session.t_stream = await session.t_client.start_stream_transcription(
        language_code="ko-KR",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )
    session.t_handler_obj = MyEventHandler(session.t_stream.output_stream, session, participant_id)
    session.t_handler_task = asyncio.create_task(session.t_handler_obj.handle_events())
    logging.info(f"[{session.session_id}] 🎙️ STT start → pid={participant_id}, index={session.index}, f_index={get_f_index_for(session, participant_id)}")

async def stop_stt(session: SessionState):
    if session.t_stream:
        try:
            await session.t_stream.input_stream.end_stream()
        except Exception:
            pass
    if session.t_handler_task:
        try:
            await session.t_handler_task
        except Exception:
            pass
    if session.t_handler_obj:
        try:
            await session.t_handler_obj.close()
        except Exception:
            pass
    session.t_client = None
    session.t_stream = None
    session.t_handler_task = None
    session.t_handler_obj = None

# ── Turn progression (참가자별 f_index) ────────────────────────────────────

def _next_pid(session: SessionState, current: Optional[str]) -> Optional[str]:
    if not session.order:
        return None
    if current not in session.order:
        return session.order[0]
    i = session.order.index(current)
    return session.order[(i + 1) % len(session.order)]

async def advance_turn(session: SessionState):
    """
    활성자(active_pid)의 f_index만 전이:
      -1 → 0 → 1 → (해당 참가자 종료: -1로 리셋, 다음 참가자 활성)
    모든 참가자가 한 번씩 끝나면 index += 1 (라운드 완료)
    """
    async with session.lock:
        if session.index >= QUESTION_COUNT:
            return

        pid = session.active_pid
        if not pid:
            return
        cur = session.participant_f_index.get(pid, -1)

        # 다음 단계 계산
        if cur < FOLLOW_UP_COUNT - 1:
            # -1 → 0 또는 0 → 1
            next_f = cur + 1
            session.participant_f_index[pid] = next_f
            logging.info(f"[{session.session_id}] f_index {pid}: {cur} → {next_f} (index={session.index})")
        else:
            # 마지막 꼬리 질문(1)까지 끝났다면 → 이 참가자 종료(-1) & 다음 참가자
            session.participant_f_index[pid] = -1
            prev_pid = pid
            next_pid = _next_pid(session, pid)
            session.active_pid = next_pid

            # 라운드 완료 판단: 다음 참가자가 order의 첫 사람이라면 한 라운드 종료
            if next_pid and session.order and session.order.index(next_pid) == 0:
                session.index += 1
                # 인터뷰 종료
                if session.index >= QUESTION_COUNT:
                    await stop_stt(session)
                    await broadcast_json(session.session_id, {"type": "finished"})
                    logging.info(f"[{session.session_id}] 🏁 인터뷰 종료")
                    return
                # 다음 index 시작 → 모든 참가자 f_index 초기화(-1)
                for k in list(session.participant_f_index.keys()):
                    session.participant_f_index[k] = -1
                logging.info(f"[{session.session_id}] ▶️ index advanced → {session.index}")

            # 활성자 변경에 맞춰 STT 전환
            await stop_stt(session)

        await emit_state(session)

# ── Connection handler ─────────────────────────────────────────────────────

async def handle_connection(ws: CustomProtocol):
    logging.info("✅ 클라이언트 연결됨")

    session_id = ws.session_id
    pid = getattr(ws, "participant_id", None)
    mode = getattr(ws, "mode", "stt")

    session = SESSIONS.get(session_id)
    if not session:
        session = SessionState(session_id=session_id)
        SESSIONS[session_id] = session

    # 참가자 등록
    session.sockets.add(ws)
    ROOMS[session_id].add(ws)
    if pid:
        session.by_pid[pid].add(ws)
        if pid not in session.order:
            session.order.append(pid)
        session.participant_f_index.setdefault(pid, -1)

    try:
        # team 초기화
        if mode == "team":
            async with session.lock:
                if session.active_pid is None and session.order:
                    session.active_pid = session.order[0]
                    session.index = 0
                    # 모든 참가자 f_index 초기화
                    for p in session.order:
                        session.participant_f_index[p] = -1
            await emit_state(session)

        # chat(문자만) 테스트 경로
        if mode == "chat":
            async for message in ws:
                if isinstance(message, str):
                    await broadcast_json(session_id, {"text": message, "participant_id": pid})
            return

        # 오디오/제어 공통
        async for message in ws:
            if isinstance(message, (bytes, bytearray)):
                if mode == "team":
                    # 비활성자의 오디오는 무시
                    if session.active_pid != pid:
                        continue

                    # 🔻 지연 STT 시작: 이 참가자의 첫 프레임이면 여기서 STT 시작
                    if session.t_stream is None or (session.t_handler_obj and session.t_handler_obj.participant_id != pid):
                        await start_stt_for(session, pid)

                    # 다른 참가자에게 중계
                    await broadcast_audio(session_id, message, exclude=ws)

                    # STT로 전송
                    if session.t_stream:
                        await session.t_stream.input_stream.send_audio_event(audio_chunk=message)
                else:
                    # 단일 stt 모드(이전 호환)
                    await broadcast_audio(session_id, message, exclude=ws)
                    if not session.t_stream:
                        async with session.lock:
                            session.active_pid = pid
                            session.index = getattr(ws, "index", 0)
                            session.participant_f_index[pid] = getattr(ws, "f_index", -1)
                            await start_stt_for(session, pid)
                    await session.t_stream.input_stream.send_audio_event(audio_chunk=message)

            else:
                # 제어 JSON
                try:
                    obj = json.loads(message)
                except Exception:
                    continue

                if mode == "team" and isinstance(obj, dict):
                    t = obj.get("type")
                    if t == "advance":
                        await advance_turn(session)
                    elif t == "set_order":
                        order = obj.get("order")
                        if isinstance(order, list) and all(isinstance(x, str) for x in order):
                            async with session.lock:
                                # 새 order 반영
                                session.order = order[:]
                                # 사라진 참가자 정리
                                for k in list(session.participant_f_index.keys()):
                                    if k not in session.order:
                                        session.participant_f_index.pop(k, None)
                                # 새 참가자 기본값
                                for k in session.order:
                                    session.participant_f_index.setdefault(k, -1)
                                # active가 order에 없으면 첫 사람으로
                                if session.active_pid not in session.order:
                                    session.active_pid = session.order[0] if session.order else None
                                    await stop_stt(session)
                            await emit_state(session)
                    elif t == "set_active":
                        new_pid = obj.get("participant_id")
                        if isinstance(new_pid, str) and new_pid in session.order:
                            async with session.lock:
                                session.active_pid = new_pid
                                session.participant_f_index.setdefault(new_pid, -1)
                                # 🔻 지연 STT: 여기서는 열지 않음
                                await stop_stt(session)
                            await emit_state(session)

    except websockets.ConnectionClosed:
        logging.info("❌ 클라이언트 연결 종료")
    finally:
        # 정리
        session.sockets.discard(ws)
        ROOMS[session_id].discard(ws)
        if pid in session.by_pid:
            session.by_pid[pid].discard(ws)
            if not session.by_pid[pid]:
                del session.by_pid[pid]
                # order에서 제거
                if pid in session.order:
                    was_active = (session.active_pid == pid)
                    session.order.remove(pid)
                    session.participant_f_index.pop(pid, None)
                    if was_active:
                        async with session.lock:
                            session.active_pid = _next_pid(session, pid)
                            await stop_stt(session)
                        await emit_state(session)

        # 세션 종료
        if not session.sockets:
            await stop_stt(session)
            SESSIONS.pop(session_id, None)
            ROOMS.pop(session_id, None)
            logging.info(f"[{session_id}] 세션 정리 완료")

# ── Entrypoint ─────────────────────────────────────────────────────────────

async def main():
    logging.info("🚀 WebSocket STT 서버 실행 중: ws://0.0.0.0:8765")
    async with serve(handle_connection, host="0.0.0.0", port=8765, create_protocol=CustomProtocol):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
