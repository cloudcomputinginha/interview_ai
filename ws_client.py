# ws_client.py
import asyncio
import websockets

#const socket = new WebSocket("wss://interviewai.play-qr.site/ws/?session_id=sess_5188b05f&index=0&f_index=-1")
async def send_audio():
    uri = f"wss://interviewai.play-qr.site/ws/?session_id=sess_7c93dc9c&index=0&f_index=1"
    async with websockets.connect(uri) as websocket:
        with open("/home/ubuntu/stt_test.wav", "rb") as f:
            chunk_size = 3200  # 16kHz PCM 16-bit mono → 약 100ms 분량
            while chunk := f.read(chunk_size):
                await websocket.send(chunk)
                await asyncio.sleep(0.1)  # 실시간처럼 보내기 위한 딜레이

if __name__ == "__main__":
    asyncio.run(send_audio())