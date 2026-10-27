import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "data": {"status": "ok"},
        "msg": "success",
    }


def test_health_still_ok(sync_client):
    response = sync_client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
