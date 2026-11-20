from pathlib import Path

import httpx

from app import externos
from app.externos import consulta_geocodificador, leer_ocupacion, titulo

FIXTURES = Path(__file__).parent / "fixtures"


def test_consulta_geocodificador_quita_codigo_postal_y_anade_madrid():
    assert consulta_geocodificador("Calle Alcala 30, 28014 Madrid") == "Calle Alcala 30, Madrid"
    assert consulta_geocodificador("Calle Alcala 30, 28014") == "Calle Alcala 30, Madrid"
    assert consulta_geocodificador("Calle Mayor 10") == "Calle Mayor 10, Madrid"
    assert consulta_geocodificador("Calle Mayor 10, Madrid") == "Calle Mayor 10, Madrid"


def test_titulo():
    assert titulo("CALLE DE LA PAZ 3") == "Calle de la Paz 3"
    assert titulo("PLAZA DEL CALLAO") == "Plaza del Callao"


def test_leer_ocupacion():
    assert leer_ocupacion((FIXTURES / "lista_parkings.xml").read_bytes()) == {5: 181}


def test_ocupacion_devuelve_vacio_si_falla(monkeypatch):
    def caido(*args, **kwargs):
        raise httpx.ConnectError("caído")
    monkeypatch.setattr(externos, "_cache_ocupacion", None)
    monkeypatch.setattr(externos.httpx, "post", caido)
    assert externos.ocupacion() == {}


def test_ocupacion_no_reintenta_en_cada_peticion_si_el_servicio_falla(monkeypatch):
    llamadas = []
    def caido(*args, **kwargs):
        llamadas.append(1)
        raise httpx.ConnectTimeout("sin respuesta")
    monkeypatch.setattr(externos, "_cache_ocupacion", None)
    monkeypatch.setattr(externos.httpx, "post", caido)
    assert externos.ocupacion() == {} and externos.ocupacion() == {}
    assert len(llamadas) == 1  # el fallo también se recuerda un rato: no se insiste contra un servidor caído


def test_leer_ocupacion_ignora_datos_mal_formados():
    xml = (FIXTURES / "lista_parkings.xml").read_bytes().replace(b"<ns2:id>3</ns2:id>", b"<ns2:id>3</ns2:id><ns2:lstOccupation><ns2:occupation><ns2:free></ns2:free></ns2:occupation></ns2:lstOccupation>")
    assert leer_ocupacion(xml) == {5: 181}  # el parking 3 trae «free» vacío: se ignora, no tumba la comprobación
