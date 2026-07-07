import boto3
import uuid
from botocore.exceptions import ClientError
from botocore.config import Config
from app.core.config import settings


def get_s3_client():
    """Return an S3-compatible client (works with MinIO, Cloudflare R2, AWS S3)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


async def upload_file(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    workspace_id: str,
) -> str:
    """
    Upload a file to S3-compatible storage.
    Returns the storage key (path) of the uploaded file.
    """
    extension = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    key = f"documents/{workspace_id}/{uuid.uuid4()}.{extension}"

    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


async def download_file(key: str) -> bytes:
    """Download a file from S3-compatible storage by its key."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise FileNotFoundError(f"File not found: {key}")
        raise


async def delete_file(key: str) -> None:
    """Delete a file from S3-compatible storage."""
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for temporary direct access to a file."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )