from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import require_roles
from src.core.roles import Role
from src.schemas.storage import StorageUsageResponse
from src.services.storage import ObjectStorageError, RustFSStorage

router = APIRouter(prefix="/storage", tags=["storage"])
admin_only = require_roles(Role.ADMIN)


@router.get("/usage", response_model=StorageUsageResponse)
def get_storage_usage(_: Annotated[object, Depends(admin_only)]) -> StorageUsageResponse:
    """Return current size and object count for the backend RustFS bucket."""
    try:
        usage = RustFSStorage().usage()
    except ObjectStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RustFS usage is unavailable",
        ) from None
    return StorageUsageResponse(
        bucket=usage.bucket,
        bucket_exists=usage.bucket_exists,
        object_count=usage.object_count,
        used_bytes=usage.used_bytes,
    )
