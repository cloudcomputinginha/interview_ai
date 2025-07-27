import asyncio
import httpx
import websockets
from websockets.legacy.server import serve
from urllib.parse import urlparse, parse_qs
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
import json
import logging

# const url = "wss://interviewai.play-qr.site/ws/?session_id=sess_5188b05f&index=0&f_index=-1";
# socket = new WebSocket(url);

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
FASTAPI_BASE_URL = "https://interviewai.play-qr.site"

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, stream, session_id, index, f_index, websocket):
        super().__init__(stream)
        self.session_id = session_id
        self.index = index
        self.f_index = f_index
        self.websocket = websocket
        self.client = httpx.AsyncClient(verify=False)

        # 🔸 누적 텍스트 버퍼
        self.full_transcript = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        for result in transcript_event.transcript.results:
            if result.is_partial:
                # 🔸 처리 중 상태 전송
                try:
                    await self.websocket.send(json.dumps({"status": "processing"}))
                    logging.info("⏳ 클라이언트에 처리 중 상태 전송 완료")
                except Exception as e:
                    logging.info(f"⚠️ 처리중 상태 전송 실패: {e}")
                continue

            # 🔸 텍스트 추출 및 누적
            new_text = result.alternatives[0].transcript.strip()
            self.full_transcript += f" {new_text}"
            self.full_transcript = self.full_transcript.strip()

            logging.info(f"📝 누적 텍스트: {self.full_transcript}")

            # 🔸 텍스트 전송
            try:
                await self.websocket.send(json.dumps({"text": new_text}))
                logging.info("📤 클라이언트에 텍스트 전송 완료")

                # 🔸 end 신호 전송
                await self.websocket.send(json.dumps({"status": "end"}))
                logging.info("✅ 클라이언트에 end 상태 전송 완료")
            except Exception as e:
                logging.info(f"⚠️ WebSocket 텍스트/종료 신호 전송 실패: {e}")

            # 🔸 FastAPI에 PATCH
            if self.f_index == -1:
                url = f"{FASTAPI_BASE_URL}/interview/session/{self.session_id}/qa/{self.index}/answer"
            else:
                url = f"{FASTAPI_BASE_URL}/interview/session/{self.session_id}/qa/{self.index}/follow-up/{self.f_index}/answer"

            response = await self.client.patch(
                url,
                content=self.full_transcript,
                headers={"Content-Type": "text/plain"}
            )
            logging.info(f"✅ FastAPI 응답: {response.status_code}, {response.text}")

class CustomProtocol(websockets.WebSocketServerProtocol):
    async def process_request(self, path, request_headers):
        # 요청 파싱
        query = parse_qs(urlparse(path).query)
        logging.info(query)
        self.session_id = query.get("session_id", [None])[0]
        self.index = int(query.get("index", [0])[0])
        self.f_index = int(query.get("f_index", [-1])[0])
        return None

async def handle_connection(websocket):
    logging.info("✅ 클라이언트 연결됨")

    session_id = websocket.session_id
    index = websocket.index
    f_index = websocket.f_index

    client = TranscribeStreamingClient(region="us-east-1")
    stream = await client.start_stream_transcription(
        language_code="ko-KR",
        media_sample_rate_hz=16000,
        media_encoding="pcm"
    )
    handler = MyEventHandler(stream.output_stream, session_id, index, f_index, websocket)

    async def send_audio():
        try:
            async for message in websocket:
                await stream.input_stream.send_audio_event(audio_chunk=message)
        except websockets.ConnectionClosed:
            logging.info("❌ 클라이언트 연결 종료")
        finally:
            await stream.input_stream.end_stream()

    await asyncio.gather(send_audio(), handler.handle_events())

async def main():
    logging.info("🚀 WebSocket STT 서버 실행 중: ws://0.0.0.0:8765")
    async with serve(
        handle_connection,
        host="0.0.0.0",
        port=8765,
        create_protocol=CustomProtocol
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
