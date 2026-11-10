from uuid import uuid4
from unittest.mock import create_autospec

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_analysis_service
from api.main import app
from domain.entities.analysis import Analysis
from infrastructure.services.analysis_service import AnalysisService, ExaminationResults


@pytest.fixture
def service():
    svc = create_autospec(AnalysisService, instance=True)   # get_results becomes an AsyncMock
    app.dependency_overrides[get_analysis_service] = lambda: svc
    yield svc
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_incomplete_examination_returns_202_with_progress(client, service):
    service.get_results.return_value = ExaminationResults(False, 2, 3, [])

    r = await client.get(f"/examinations/{uuid4()}/analyses")

    assert r.status_code == 202
    assert r.json() == {"status": "processing", "received": 2, "expected": 3}


async def test_examination_without_analyses_reports_unknown_expected(client, service):
    service.get_results.return_value = ExaminationResults(False, 0, None, [])

    r = await client.get(f"/examinations/{uuid4()}/analyses")

    assert r.status_code == 202
    assert r.json()["expected"] is None


async def test_complete_examination_returns_200_with_serialized_analyses(client, service):
    exam = uuid4()
    analyses = [Analysis(1, exam, 1.5, 0.2, 0.9, 2), Analysis(2, exam, 2.5, 0.8, None, 2)]
    service.get_results.return_value = ExaminationResults(True, 2, 2, analyses)

    r = await client.get(f"/examinations/{exam}/analyses")

    assert r.status_code == 200
    assert r.json() == {
        "examination_id": str(exam),
        "total_analyses_count": 2,
        "analyses": [
            {"analysis_id": 1, "time_stamp": 1500, "result": 0.2, "confidence": 0.9},
            {"analysis_id": 2, "time_stamp": 2500, "result": 0.8, "confidence": None},
        ],
    }


async def test_service_is_queried_with_the_uuid_from_the_path(client, service):
    exam = uuid4()
    service.get_results.return_value = ExaminationResults(False, 0, None, [])

    await client.get(f"/examinations/{exam}/analyses")

    service.get_results.assert_awaited_once_with(exam)


async def test_invalid_uuid_returns_422_without_calling_service(client, service):
    r = await client.get("/examinations/not-a-uuid/analyses")

    assert r.status_code == 422
    service.get_results.assert_not_awaited()