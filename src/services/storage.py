import os
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

logger = Logger()


class StorageService:
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.bucket_name = os.environ["UPLOAD_BUCKET_NAME"]

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for uploading a file"""
        try:
            url = self.s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": "image/*",  # Allow any image type
                },
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            raise

    def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file"""
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating download URL: {str(e)}")
            raise
