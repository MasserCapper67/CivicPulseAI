import pytest
from fastapi.testclient import TestClient

from app import externos

CALLE_MAYOR_10 = {"lat": 40.4165, "lng": -3.7060, "muniCode": "28079", "tip_via": "CALLE", "address": "MAYOR",
                  "portalNumber": 10, "postalCode": "28013", "poblacion": "Madrid"}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(externos, "geocodificar", lambda direccion: CALLE_MAYOR_10)
    monkeypatch.setattr(externos, "ocupacion", lambda: {})  # como con el SOAP caído
    from app.main import app
    return TestClient(app)


def test_solo_parking_trae_alternativas(cliente):
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "B", "padron": "fuera"}).json()
    assert r["veredicto"] == "solo_parking" and r["alternativas"] and r["como_llegar"] is None and r["horas"] == 2
    assert r["paradas_cercanas"] and r["destino"]["direccion"] == "Calle Mayor 10, 28013 Madrid"


def test_puede_trae_ruta_y_no_alternativas(cliente):
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "ECO", "padron": "fuera"}).json()
    assert r["veredicto"] == "puede" and r["alternativas"] == [] and r["como_llegar"].startswith("https://www.google.com/maps/dir/")


def test_comprobar_sin_ocupacion(cliente):  # ocupación vacía (SOAP caído): sigue habiendo alternativas
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "B", "padron": "fuera", "horas": 4}).json()
    assert r["alternativas"] and all(a["plazas_libres"] is None for a in r["alternativas"]) and r["horas"] == 4


@pytest.mark.parametrize("cuerpo", [
    {"direccion": "x", "etiqueta": "B", "padron": "fuera", "horas": 0},
    {"direccion": "x", "etiqueta": "B", "padron": "fuera", "horas": 25},
    {"direccion": "x", "etiqueta": "B", "matricula": "0001CVG", "padron": "fuera"},
])
def test_entradas_invalidas(cliente, cuerpo):
    assert cliente.post("/api/comprobar", json=cuerpo).status_code == 422


def test_cabeceras_y_parkings(cliente):
    r = cliente.get("/api/parkings")
    assert r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]
    assert len(r.json()["features"]) >= 50
