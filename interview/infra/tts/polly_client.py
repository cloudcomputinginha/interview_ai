import os
import uuid
import boto3

class PollyClient:
    def __init__(self):
        self.polly = boto3.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.s3 = boto3.client("s3")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")

        if not self.bucket_name:
            raise ValueError("S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")

    def synthesize_to_s3(self, text: str, voice_id: str = "Seoyeon", filename: str = None) -> str:
        """
        주어진 텍스트를 음성으로 변환하여 S3에 지정된 이름으로 업로드하고 S3 URI를 반환합니다.
        """
        response = self.polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id
        )

        # 기본 파일 이름 지정
        if filename is None:
            filename = f"{uuid.uuid4().hex}.mp3"

        local_path = f"/tmp/{filename}"

        # 파일 저장
        with open(local_path, "wb") as f:
            f.write(response["AudioStream"].read())

        # S3 업로드
        self.s3.upload_file(local_path, self.bucket_name, filename)

        # 로컬 파일 삭제
        os.remove(local_path)

        return f"{filename}"