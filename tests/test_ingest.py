from pathlib import Path

from ingest.aparcamientos import leer_tarifas
from ingest.estaciones import leer_estaciones
from tests.datos import TARIFAS_RECUERDO

FIXTURES = Path(__file__).parent / "fixtures"


def punto(nombre, lineas, corona, lng, lat):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"DENOMINACION": nombre, "LINEAS": lineas, "CORONATARIFARIA": corona}}


def test_leer_tarifas():  # 4 tramos reales (uno con «MINUTOS» en mayúsculas) + un «TARIFA ACCESO» que se descarta
    assert leer_tarifas((FIXTURES / "detalle_parking.xml").read_bytes()) == TARIFAS_RECUERDO


def test_leer_estaciones_funde_repetidas():
    fc = {"features": [punto("SOL", "1, 2, 3", "A", -3.70326, 40.41687), punto("SOL", "1, 2, 3", "A", -3.70326, 40.41684)]}
    assert leer_estaciones(fc, "Metro") == [{"nombre": "Sol", "modo": "Metro", "lineas": ["L1", "L2", "L3"],
                                             "corona": "A", "lat": 40.41687, "lng": -3.70326}]


def test_leer_estaciones_cercanias_sin_corona():
    fc = {"features": [punto("PUERTA DEL SUR", "C-5", " ", -3.8, 40.3)]}
    assert leer_estaciones(fc, "Cercanías") == [{"nombre": "Puerta del Sur", "modo": "Cercanías", "lineas": ["C-5"],
                                                 "corona": None, "lat": 40.3, "lng": -3.8}]


def test_leer_estaciones_descarta_las_que_no_tienen_nombre():  # en el servicio del CRTM hay registros sin DENOMINACION
    fc = {"features": [punto(None, "1", "A", -3.7, 40.4), punto("SOL", "1", "A", -3.70326, 40.41687)]}
    assert [e["nombre"] for e in leer_estaciones(fc, "Metro")] == ["Sol"]
