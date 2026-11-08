from unittest.mock import AsyncMock
from uuid import uuid4

from domain.entities.analysis import Analysis
from infrastructure.services.analysis_service import AnalysisService, ExaminationResults
import pytest




def make_analysis(i: int, exam, total: int) -> Analysis:
    return Analysis(i, exam, float(i), 0.5, 0.9, total)


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def service(repo):
    return AnalysisService(repo)


async def test_no_analyses_means_incomplete_with_unknown_expected(service, repo):
    repo.list_for_examination.return_value = []

    result = await service.get_results(uuid4())

    assert result == ExaminationResults(
        is_complete=False, received=0, expected=None, analyses=[]
    )


async def test_partial_results_are_incomplete(service, repo):
    exam = uuid4()
    analyses = [make_analysis(i, exam, total=3) for i in (1, 2)]
    repo.list_for_examination.return_value = analyses

    result = await service.get_results(exam)

    assert (result.is_complete, result.received, result.expected) == (False, 2, 3)
    assert result.analyses == analyses


async def test_results_are_complete_when_received_equals_expected(service, repo):
    exam = uuid4()
    repo.list_for_examination.return_value = [make_analysis(i, exam, total=2) for i in (1, 2)]

    result = await service.get_results(exam)

    assert result.is_complete is True


async def test_results_are_complete_when_received_exceeds_expected(service, repo):
    exam = uuid4()
    repo.list_for_examination.return_value = [make_analysis(i, exam, total=2) for i in (1, 2, 3)]

    result = await service.get_results(exam)

    assert (result.is_complete, result.received, result.expected) == (True, 3, 2)


async def test_expected_is_taken_from_first_analysis(service, repo):
    exam = uuid4()
    repo.list_for_examination.return_value = [
        make_analysis(1, exam, total=5),
        make_analysis(2, exam, total=9),
    ]

    result = await service.get_results(exam)

    assert result.expected == 5


async def test_queries_repository_for_given_examination(service, repo):
    exam = uuid4()
    repo.list_for_examination.return_value = []

    await service.get_results(exam)

    repo.list_for_examination.assert_awaited_once_with(exam)