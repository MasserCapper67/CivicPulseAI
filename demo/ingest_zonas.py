"""Genera data/zonas.geojson y static/geo/camaras.geojson desde los ficheros oficiales del Ayuntamiento.

Necesita ogr2ogr (GDAL): convierte los SHP (ETRS89 UTM 30N) a GeoJSON en lat/lng.
Uso: .venv/bin/python ingest_zonas.py
"""
import json
import os
import subprocess
import urllib.request

import shapely

AQUI = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(AQUI, "data", "raw", "madrid")
FUENTES = {
    "zbe_camaras.zip": "https://datos.madrid.es/dataset/300654-0-circulacion-camaras-trafico/resource/300654-0-circulacion-camaras-trafico-zip/download/300654-0-circulacion-camaras-trafico-zip.zip",
    "eliptica.zip": "https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZBEDEP/ZBEDEP_Plaza_Eliptica.zip",
    "centro_perimetro.zip": "https://datos.madrid.es/dataset/300229-0-trafico-madrid-central/resource/300229-5-trafico-madrid-central-zip/download/300229-5-trafico-madrid-central-zip.zip",
    "centro_camaras.geojson": "https://datos.madrid.es/dataset/300229-0-trafico-madrid-central/resource/300229-0-trafico-madrid-central-geo/download/300229-0-trafico-madrid-central-geo.geo",
}
ELIPTICA = "/vsizip/" + os.path.join(RAW, "eliptica.zip") + "/ZBEDEP_Plaza_Eliptica/ZBEDEP_Plaza_Eliptica_"
SIMPLIFICAR = 0.00002  # ~2 m: reduce el tamaño del GeoJSON sin cambiar los veredictos


def descargar():
    os.makedirs(RAW, exist_ok=True)
    for nombre, url in FUENTES.items():
        ruta = os.path.join(RAW, nombre)
        if not os.path.exists(ruta):
            urllib.request.urlretrieve(url, ruta)
            print("descargado:", nombre)


def leer(ruta):
    """Cualquier capa que lea GDAL (también dentro de un ZIP) -> features GeoJSON en lat/lng."""
    salida = subprocess.run(["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326", "/vsistdout/", ruta],
                            check=True, capture_output=True).stdout
    return json.loads(salida)["features"]


def forma(feature):
    return shapely.geometry.shape(feature["geometry"])


def main():
    descargar()
    zbe_tm = leer("/vsizip/" + os.path.join(RAW, "zbe_camaras.zip") + "/ZBE_TM.shp")
    # Via_Out=1 son los corredores de autovías que quedan fuera de la ZBE (interpretación: confirmar en la ordenanza).
    zbe = shapely.union_all([forma(f) for f in zbe_tm if f["properties"]["Via_Out"] == 0])
    centro = shapely.Polygon(forma(leer("/vsizip/" + os.path.join(RAW, "centro_perimetro.zip") + "/Madrid_Central.shp")[0]).coords)
    eliptica = shapely.union_all([forma(f) for f in leer(ELIPTICA + "Limite.shp")])

    zonas = [
        ("zbe_madrid", "ZBE Madrid", zbe, "datos.madrid.es 300654 · ZBE_TM"),
        ("zbedep_centro", "ZBEDEP Distrito Centro", centro, "datos.madrid.es 300229 · perímetro de 2018"),
        ("zbedep_eliptica", "ZBEDEP Plaza Elíptica", eliptica, "geoportal.madrid.es · ZBEDEP_Plaza_Eliptica_Limite"),
    ]
    # Validar antes de escribir: puntos conocidos tienen que caer donde toca.
    sol, eliptica_pl, retiro, getafe = (shapely.Point(p) for p in [(-3.7035, 40.4168), (-3.7183, 40.3853), (-3.6844, 40.4153), (-3.7326, 40.3057)])
    assert zbe.contains(sol) and centro.contains(sol) and not eliptica.contains(sol)
    assert zbe.contains(eliptica_pl) and eliptica.contains(eliptica_pl) and not centro.contains(eliptica_pl)
    assert zbe.contains(retiro) and not centro.contains(retiro) and not eliptica.contains(retiro)
    assert not zbe.contains(getafe)

    with open(os.path.join(AQUI, "data", "zonas.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": shapely.geometry.mapping(g.simplify(SIMPLIFICAR)),
             "properties": {"id": zona, "nombre": nombre, "fuente": fuente}}
            for zona, nombre, g, fuente in zonas]}, f, ensure_ascii=False)

    camaras = (
        [("ZBE Madrid", f["properties"]["LUGAR_INFR"], f) for f in leer("/vsizip/" + os.path.join(RAW, "zbe_camaras.zip") + "/ZBE_MADRID_CAMARAS.shp")]
        + [("Distrito Centro", f["properties"]["title"], f) for f in leer(os.path.join(RAW, "centro_camaras.geojson"))]
        + [("Plaza Elíptica", f["properties"]["NOMBRE"], f) for f in leer(ELIPTICA + "Puntos_Control_Acceso.shp")]
    )
    os.makedirs(os.path.join(AQUI, "static", "geo"), exist_ok=True)
    with open(os.path.join(AQUI, "static", "geo", "camaras.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": c["geometry"], "properties": {"zona": zona, "nombre": nombre}}
            for zona, nombre, c in camaras]}, f, ensure_ascii=False)
    print(f"ok: {len(zonas)} zonas, {len(camaras)} cámaras")


if __name__ == "__main__":
    main()
