"""Zonas de bajas emisiones y geometría: ¿en qué zonas cae un punto?, distancias en metros."""
import json
import math
from pathlib import Path

import shapely

RAIZ = Path(__file__).resolve().parents[1]
# Escala local de Madrid (latitud 40,42°): de grados a metros con error despreciable dentro de la ciudad.
METROS_POR_GRADO = (math.cos(math.radians(40.42)) * 111_320, 110_574)

ZONAS_GEOJSON = json.loads((RAIZ / "data" / "zonas.geojson").read_text(encoding="utf-8"))
ZONAS = {}  # id -> (nombre, geometría preparada para consultas rápidas de «¿está dentro?»), en el orden del fichero
for feature in ZONAS_GEOJSON["features"]:
    geometria = shapely.geometry.shape(feature["geometry"])
    shapely.prepare(geometria)
    ZONAS[feature["properties"]["id"]] = (feature["properties"]["nombre"], geometria)


# Término municipal de Madrid (la ZBE general con sus corredores de autovía): su borde exterior es el límite real.
TERMINO = shapely.geometry.shape(json.loads((RAIZ / "data" / "termino_municipal.geojson").read_text(encoding="utf-8"))["geometry"])


def zonas_en(lng, lat):
    punto = shapely.Point(lng, lat)
    return [zona for zona, (_, geometria) in ZONAS.items() if geometria.contains(punto)]


def a_metros(geometria):
    return shapely.transform(geometria, lambda c: c * METROS_POR_GRADO)


def a_grados(geometria):
    return shapely.transform(geometria, lambda c: c / METROS_POR_GRADO)


def distancia_m(lng1, lat1, lng2, lat2):
    return math.hypot((lng1 - lng2) * METROS_POR_GRADO[0], (lat1 - lat2) * METROS_POR_GRADO[1])
