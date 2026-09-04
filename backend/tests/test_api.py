from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_bursaries_by_course():
    r = client.get("/bursaries", params={"course": "Computer Science"})
    assert r.status_code == 200

    results = r.json()
    assert len(results) > 0

    for bursary in results:
        assert "Computer Science" in "".join(bursary["fields_of_study"]) \
            or any(
                "computer science" in field.lower()
                for field in bursary["fields_of_study"]
            )


def test_list_bursaries_requires_course():
    r = client.get("/bursaries", params={"course": ""})
    assert r.status_code == 400


def test_get_bursary_detail():
    results = client.get(
        "/bursaries", params={"course": "Computer Science"}
    ).json()

    bursary_id = results[0]["id"]

    r = client.get(f"/bursaries/{bursary_id}")
    assert r.status_code == 200

    detail = r.json()
    assert detail["id"] == bursary_id
    assert "eligibility" in detail
    assert "application_instructions" in detail


def test_get_bursary_detail_not_found():
    r = client.get("/bursaries/999999")
    assert r.status_code == 404


def test_chat_without_lm_studio_running_fails_cleanly():
    """
    With no LM Studio server reachable, the chat endpoint should
    return a clean 503 rather than crashing the app.
    """

    r = client.post(
        "/chat",
        json={"course": "Computer Science", "message": "hello"},
    )
    assert r.status_code == 503
    assert "LM Studio" in r.json()["detail"]
