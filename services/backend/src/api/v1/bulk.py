import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.schemas.bulk import BulkDeleteResponse, BulkExaminationRequest
from src.services import audit as audit_service
from src.services import examinations as examinations_service
from src.services.storage import ObjectStorageError, RustFSStorage

router = APIRouter(prefix="/examinations", tags=["bulk operations"])
admin_only = Depends(require_roles(Role.ADMIN))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/bulk-delete", response_model=BulkDeleteResponse, dependencies=[admin_only])
def bulk_delete(
    payload: BulkExaminationRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> BulkDeleteResponse:
    try:
        deleted = examinations_service.soft_delete_examinations(medical_db, payload.examination_ids)
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more examinations were not found") from None
    for examination in deleted:
        audit_service.log(audit_db, event_code="EXAMINATION_DELETED", user_id=current_user.id, resource_type="EXAMINATION", resource_id=examination.id, metadata={"action": "BULK_DELETE", "count": len(deleted)}, ip_address=_client_ip(request))
    return BulkDeleteResponse(deleted_count=len(deleted), examination_ids=[item.id for item in deleted])


@router.post("/bulk-export", dependencies=[admin_only])
def bulk_export(
    payload: BulkExaminationRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> StreamingResponse:
    try:
        examinations = [examinations_service.get_examination(medical_db, examination_id) for examination_id in payload.examination_ids]
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more examinations were not found") from None
    archive = BytesIO()
    storage = RustFSStorage()
    try:
        with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
            for examination in examinations:
                folder = str(examination.id)
                metadata = {"id": str(examination.id), "patient_id": str(examination.patient_id), "original_filename": examination.original_filename, "file_format": examination.file_format, "file_size_bytes": examination.file_size_bytes, "examination_date": examination.examination_date.isoformat() if examination.examination_date else None, "sampling_frequency": examination.sampling_frequency, "processing_status": examination.processing_status}
                zip_file.writestr(f"{folder}/metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
                zip_file.writestr(f"{folder}/{examination.original_filename}", storage.download(bucket=examination.storage_bucket, key=examination.storage_key))
    except ObjectStorageError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from None
    archive.seek(0)
    audit_service.log(audit_db, event_code="DATA_EXPORTED", user_id=current_user.id, resource_type="EXAMINATION", metadata={"action": "BULK_EXPORT", "examination_count": len(examinations)}, ip_address=_client_ip(request))
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=neurotrace-examinations.zip"})
