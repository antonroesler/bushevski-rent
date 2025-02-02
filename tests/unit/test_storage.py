import base64
from uuid import UUID

import pytest
from botocore.exceptions import ClientError

from utils.storage import StorageService


def test_upload_drivers_license(s3_bucket: str, ssm):
    """Test uploading driver's license."""
    service = StorageService()

    # Create test data
    booking_id = UUID("12345678-1234-5678-1234-567812345678")
    customer_email = "test@example.com"
    file_content = base64.b64encode(b"test file content").decode()
    file_type = "application/pdf"

    # Test successful upload
    key = service.upload_drivers_license(
        booking_id=booking_id,
        customer_email=customer_email,
        file_content=file_content,
        file_type=file_type,
    )

    assert key == f"drivers-licenses/{booking_id}/{customer_email}.pdf"

    # Test invalid file type
    with pytest.raises(ValueError, match="Unsupported file type"):
        service.upload_drivers_license(
            booking_id=booking_id,
            customer_email=customer_email,
            file_content=file_content,
            file_type="invalid/type",
        )

    # Test invalid base64 content
    with pytest.raises(ValueError, match="Invalid file content"):
        service.upload_drivers_license(
            booking_id=booking_id,
            customer_email=customer_email,
            file_content="invalid base64",
            file_type=file_type,
        )


def test_get_download_url(s3_bucket: str, ssm):
    """Test generating download URLs."""
    service = StorageService()

    # Upload a test file first
    booking_id = UUID("12345678-1234-5678-1234-567812345678")
    customer_email = "test@example.com"
    file_content = base64.b64encode(b"test file content").decode()
    key = service.upload_drivers_license(
        booking_id=booking_id,
        customer_email=customer_email,
        file_content=file_content,
        file_type="application/pdf",
    )

    # Test getting URL
    url = service.get_download_url(key)
    assert url.startswith("https://")
    assert s3_bucket in url
    assert key in url

    # Test getting URL with custom expiration
    url = service.get_download_url(key, expires_in=7200)
    assert url.startswith("https://")
    assert s3_bucket in url
    assert key in url

    # Test getting URL for non-existent key
    with pytest.raises(ClientError):
        service.get_download_url("non-existent-key")


def test_delete_file(s3_bucket: str, ssm):
    """Test deleting files."""
    service = StorageService()

    # Upload a test file first
    booking_id = UUID("12345678-1234-5678-1234-567812345678")
    customer_email = "test@example.com"
    file_content = base64.b64encode(b"test file content").decode()
    key = service.upload_drivers_license(
        booking_id=booking_id,
        customer_email=customer_email,
        file_content=file_content,
        file_type="application/pdf",
    )

    # Test successful deletion
    service.delete_file(key)

    # Test deleting non-existent file (should not raise error)
    service.delete_file(key)
