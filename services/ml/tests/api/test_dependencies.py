from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.dependencies import get_analysis_service


@pytest.mark.asyncio
async def test_dependency_builds_service_on_request_scoped_session():
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    request = MagicMock()
    request.app.state.session_factory = factory

    with patch("api.dependencies.SqlAlchemyAnalysisRepository") as repo_cls, \
         patch("api.dependencies.AnalysisService") as service_cls:
        gen = get_analysis_service(request)
        service = await gen.__anext__()

        repo_cls.assert_called_once_with(session)
        service_cls.assert_called_once_with(repo_cls.return_value)
        assert service is service_cls.return_value
        factory.return_value.__aexit__.assert_not_awaited()   # session open during the request

        await gen.aclose()

    factory.return_value.__aexit__.assert_awaited_once()