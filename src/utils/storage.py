import base64
from datetime import datetime
from uuid import UUID

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()


class StorageService:
    def __init__(self):
        self.s3 = boto3.client("s3")
        self.bucket_name = boto3.client("ssm").get_parameter(Name="/bushevski/s3/documents_bucket")[
            "Parameter"
        ]["Value"]

    def upload_drivers_license(
        self, booking_id: UUID, customer_email: str, file_content: str, file_type: str
    ) -> str:
        """Upload driver's license file to S3.

        Args:
            booking_id: The booking ID
            customer_email: Customer's email
            file_content: Base64 encoded file content
            file_type: File type (e.g., 'image/jpeg', 'application/pdf')

        Returns:
            S3 object key
        """
        # Decode base64 content
        try:
            file_data = base64.b64decode(file_content)
        except Exception as e:
            logger.error(f"Failed to decode file content: {e!s}")
            raise ValueError("Invalid file content") from e

        # Generate S3 key
        file_extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "application/pdf": "pdf",
        }.get(file_type)

        if not file_extension:
            raise ValueError(f"Unsupported file type: {file_type}")

        key = f"drivers-licenses/{booking_id}/{customer_email}.{file_extension}"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                ContentType=file_type,
                Metadata={
                    "booking_id": str(booking_id),
                    "customer_email": customer_email,
                    "upload_date": datetime.utcnow().isoformat(),
                },
            )
            logger.info(f"Uploaded driver's license for booking {booking_id}")
            return key
        except Exception as e:
            logger.error(f"Failed to upload file: {e!s}")
            raise

    def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for downloading a file.

        Args:
            key: S3 object key
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL
        """
        try:
            url = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL: {e!s}")
            raise

    def delete_file(self, key: str) -> None:
        """Delete a file from S3.

        Args:
            key: S3 object key
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted file: {key}")
        except ClientError as e:
            logger.error(f"Failed to delete file: {e!s}")
            raise
