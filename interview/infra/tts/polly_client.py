import os
import uuid
import boto3
import tempfile
from interview.domain.tts.tts_client import TTSClient

class PollyClient(TTSClient):
    def __init__(self):
        self.polly = boto3.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.s3 = boto3.client("s3")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")

        if not self.bucket_name:
            raise ValueError("S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")

    def synthesize_to_s3(self, text: str, voice_id: str = "Seoyeon", filename: str = None) -> str:
        try:
            response = self.polly.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=voice_id
            )
        except Exception as e:
            raise RuntimeError(f"Failed to synthesize speech: {str(e)}")

        if filename is None:
            filename = f"{uuid.uuid4().hex}.mp3"

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, filename)
            
            try:
                with open(local_path, "wb") as f:
                    f.write(response["AudioStream"].read())
                
                self.s3.upload_file(local_path, self.bucket_name, filename)
            except Exception as e:
                raise RuntimeError(f"Failed to save or upload audio file: {str(e)}")

        return f"{filename}"