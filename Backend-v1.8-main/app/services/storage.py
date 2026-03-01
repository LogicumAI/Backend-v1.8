import json
import boto3
from datetime import datetime, timezone
from botocore.config import Config
from app.core import config

class S3StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT,
            region_name=config.S3_REGION,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            use_ssl=True,
            config=Config(s3={"addressing_style": "path"}),
        )
        self.bucket = config.S3_BUCKET

    async def save_message(self, user_id: int, chat_id: int, role: str, content: str, sequence: int):
        """
        Saves a message to S3 in the path: users/{user_id}/chats/{chat_id}/{timestamp}_{sequence}.json
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"users/{user_id}/chats/{chat_id}/{timestamp}_{sequence}.json"
        
        payload = {
            "user_id": str(user_id),
            "chat_id": str(chat_id),
            "role": role,
            "content": content,
            "sequence": sequence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(payload, ensure_ascii=False),
                ContentType="application/json"
            )
            return key
        except Exception as e:
            # For now, we just log the error to avoid breaking the chat flow
            print(f"Error saving message to S3: {e}")
            return None

# Singleton instance
storage_service = S3StorageService()
