from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.dependencies import get_analysis_service
from api.schemas import AnalysesResponse, AnalysisDto
from infrastructure.services.analysis_service import AnalysisService


router = APIRouter(prefix="/examinations", tags=["analyses"])

@router.get(
    "/{examination_id}/analyses",
    response_model=AnalysesResponse,
    responses={202: {"description": "Analyses are not complete yet"}},
)
async def get_analyses(
    examination_id: UUID,
    service: AnalysisService = Depends(get_analysis_service),
):
    results = await service.get_results(examination_id)

    if not results.is_complete:
        return JSONResponse(
            status_code=202,
            content={
                "status": "processing",
                "received": results.received,
                "expected": results.expected,
            },
        )

    return AnalysesResponse(
        examination_id=examination_id,
        total_analyses_count=results.expected,
        analyses=[AnalysisDto.from_domain(a) for a in results.analyses],
    )