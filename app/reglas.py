"""Reglas de acceso (data/reglas.json, escritas a mano desde la ordenanza) y veredicto en un punto."""
import json

import shapely

from app.geo import RAIZ, ZONAS

REGLAS = json.loads((RAIZ / "data" / "reglas.json").read_text(encoding="utf-8"))
GRAVEDAD = {"puede": 0, "solo_parking": 1, "no_puede": 2}


def regla(zona, etiqueta, padron, hoy):
    """La única regla vigente hoy para esa combinación (tests/test_reglas.py comprueba que siempre hay una)."""
    hoy = hoy.isoformat()
    vigentes = [r for r in REGLAS["reglas"]
                if r["zona"] == zona and etiqueta in r["etiquetas"] and padron in r["padron"]
                and (r["desde"] or "0000") <= hoy <= (r["hasta"] or "9999")]
    assert len(vigentes) == 1, (zona, etiqueta, padron, hoy, vigentes)
    return vigentes[0]


def veredicto(lng, lat, etiqueta, padron, hoy):
    """Evalúa todas las zonas que contienen el punto; gana la más restrictiva y, si empatan, la más
    específica (en zonas.geojson las ZBEDEP van después de la ZBE general). None si no cae en ninguna."""
    punto = shapely.Point(lng, lat)
    aplicables = []
    for orden, (zona, (_, geometria)) in enumerate(ZONAS.items()):
        if geometria.contains(punto):
            r = regla(zona, etiqueta, padron, hoy)
            aplicables.append((GRAVEDAD[r["veredicto"]], orden, r, zona))
    if not aplicables:
        return None
    _, _, r, zona = max(aplicables)
    return r, zona
