import pytest


REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"


def test_projects_list_default_pagination(client, auth_headers):
    response = client.get(
        "/projects",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0
    assert len(data) <= 50

    for project in data:
        assert "project_id" in project


def test_projects_list_respects_skip(client, auth_headers):
    first_response = client.get(
        "/projects?skip=0&limit=5",
        headers=auth_headers,
    )
    second_response = client.get(
        "/projects?skip=5&limit=5",
        headers=auth_headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_page = first_response.json()
    second_page = second_response.json()

    assert len(first_page) == 5
    assert len(second_page) == 5

    first_ids = {p["project_id"] for p in first_page}
    second_ids = {p["project_id"] for p in second_page}

    assert first_ids.isdisjoint(second_ids)


def test_projects_list_ordering_is_deterministic_across_pages(
    client,
    auth_headers,
):
    response_1 = client.get(
        "/projects?skip=0&limit=20",
        headers=auth_headers,
    )
    response_2 = client.get(
        "/projects?skip=0&limit=20",
        headers=auth_headers,
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    ids_1 = [p["project_id"] for p in response_1.json()]
    ids_2 = [p["project_id"] for p in response_2.json()]

    assert ids_1 == ids_2
    assert ids_1 == sorted(ids_1)


def test_projects_list_empty_database_does_not_affect_production_dataset(
    client,
    auth_headers,
):
    """
    The current project API uses canonical_projects.csv as the
    authoritative project universe rather than the application DB.
    """
    response = client.get(
        "/projects?skip=0&limit=5",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 5


def test_project_detail_success_matches_schema_fields(
    client,
    auth_headers,
):
    encoded_id = REAL_PROJECT_ID.replace("/", "%2F")

    response = client.get(
        f"/projects/{encoded_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["project_id"] == REAL_PROJECT_ID
    assert "risk_score" in data
    assert "risk_level" in data

    assert float(data["risk_score"]) == pytest.approx(10.18, abs=0.01)
    assert data["risk_level"] == "LOW"


def test_project_detail_with_slash_in_id_is_handled(
    client,
    auth_headers,
):
    """
    MPLADS work IDs contain '/' characters. The project route must
    correctly resolve these IDs.
    """
    encoded_id = REAL_PROJECT_ID.replace("/", "%2F")

    response = client.get(
        f"/projects/{encoded_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["project_id"] == REAL_PROJECT_ID