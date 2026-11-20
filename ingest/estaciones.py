"""Genera data/estaciones.json: estaciones de Metro y Cercanías del Consorcio Regional de Transportes (CRTM).

Uso: .venv/bin/python -m ingest.estaciones
"""
import json

import httpx

from app.externos import titulo
from app.vehiculo import RAIZ
from ingest import registrar_fuente

SALIDA = RAIZ / "data" / "estaciones.json"
SERVICIO = ("https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/{red}/FeatureServer/0/query"
            "?where=1%3D1&outFields=DENOMINACION,LINEAS,CORONATARIFARIA&outSR=4326&f=geojson")
REDES = {"M4_Red": "Metro", "M5_Red": "Cercanías"}


def leer_estaciones(geojson, modo):
    """Una entrada por estación: el CRTM repite las de varias líneas (una por línea) y aquí se funden."""
    estaciones = {}
    for f in geojson["features"]:
        p = f["properties"]
        if not p.get("DENOMINACION"):
            continue  # el servicio trae registros sin nombre ni líneas: no son estaciones utilizables
        lineas = [l.strip() for l in (p.get("LINEAS") or "").split(",") if l.strip()]
        if modo == "Metro":
            lineas = [f"L{l}" for l in lineas]
        nombre = titulo(p["DENOMINACION"])
        if nombre in estaciones:
            estaciones[nombre]["lineas"] += [l for l in lineas if l not in estaciones[nombre]["lineas"]]
            continue
        lng, lat = f["geometry"]["coordinates"]
        estaciones[nombre] = {"nombre": nombre, "modo": modo, "lineas": lineas,
                              "corona": (p.get("CORONATARIFARIA") or "").strip() or None, "lat": lat, "lng": lng}
    return list(estaciones.values())


def main():
    estaciones = []
    for red, modo in REDES.items():
        r = httpx.get(SERVICIO.format(red=red), timeout=60)
        r.raise_for_status()
        leidas = leer_estaciones(r.json(), modo)
        assert len(leidas) >= 100, f"{modo}: demasiado pocas estaciones ({len(leidas)})"
        estaciones += leidas
        registrar_fuente(f"estaciones/{modo}", SERVICIO.format(red=red), None)
        print(f"{modo}: {len(leidas)} estaciones")
    SALIDA.write_text(json.dumps(estaciones, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
