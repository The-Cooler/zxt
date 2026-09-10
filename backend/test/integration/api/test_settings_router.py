"""
Integration tests for settings router endpoints.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_legacy_reranker_endpoint_is_not_registered(test_client, standard_user):
    public_response = await test_client.get("/api/settings/rerankers")
    assert public_response.status_code == 404

    owner_response = await test_client.get("/api/settings/rerankers", headers=standard_user["headers"])
    assert owner_response.status_code == 404


async def test_legacy_reranker_endpoint_still_returns_not_found(test_client, admin_headers):
    response = await test_client.get("/api/settings/rerankers", headers=admin_headers)
    assert response.status_code == 404, response.text
