from fastapi.testclient import TestClient

from app.api import ml as ml_api
from app.api import street_view as street_view_api
from app.integrations.street_view import StreetViewClient
from app.main import app


def test_street_view_metadata_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        street_view_api, "street_view_client", StreetViewClient(api_key="")
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/street-view/metadata", params={"lat": -23.55, "lon": -46.63}
        )

    assert response.status_code == 200
    assert response.json() == {"available": False, "status": "NOT_CONFIGURED"}


def test_street_view_image_without_key_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(
        street_view_api, "street_view_client", StreetViewClient(api_key="")
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/street-view/image", params={"lat": -23.55, "lon": -46.63}
        )

    assert response.status_code == 503


def test_street_view_rejects_invalid_coordinates() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/street-view/metadata", params={"lat": 91, "lon": 0}
        )

    assert response.status_code == 422


def test_training_metrics_endpoint_without_report(monkeypatch) -> None:
    monkeypatch.setattr(ml_api, "load_training_report", lambda: None)

    with TestClient(app) as client:
        response = client.get("/api/v1/ml/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "python -m app.ml.train" in body["message"]
