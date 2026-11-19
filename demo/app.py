"""PROTOTIPO DESECHABLE · ¿Puedo entrar con mi coche? (ZBE Madrid).

Arranque: .venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
"""
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import date
from functools import lru_cache
from typing import Literal

import httpx
import shapely
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from ingest_dgt import CODIGOS, DB

AQUI = os.path.dirname(os.path.abspath(__file__))
CARTOCIUDAD = "https://www.cartociudad.es/geocoder/api/geocoder/find"
CARTOCIUDAD_CANDIDATOS = "https://www.cartociudad.es/geocoder/api/geocoder/candidates"
MUNICIPIO_MADRID = "28079"
Etiqueta = Literal["CERO", "ECO", "C", "B", "A", "H"]  # H = vehículo histórico (pegatina H)
Padron = Literal["fuera", "madrid", "centro"]
GRAVEDAD = {"puede": 0, "solo_parking": 1, "no_puede": 2}

with open(os.path.join(AQUI, "data", "reglas.json"), encoding="utf-8") as f:
    REGLAS = json.load(f)
with open(os.path.join(AQUI, "data", "zonas.geojson"), encoding="utf-8") as f:
    ZONAS_GEOJSON = json.load(f)
ZONAS = {}  # id -> (nombre, geometría preparada para consultas rápidas de «¿está dentro?»)
for feature in ZONAS_GEOJSON["features"]:
    geometria = shapely.geometry.shape(feature["geometry"])
    shapely.prepare(geometria)
    ZONAS[feature["properties"]["id"]] = (feature["properties"]["nombre"], geometria)


def traducir(codigo):
    """Código DGT -> (etiqueta, es_moto). '16MC' -> ('C', True); 'SIN DISTINTIVO' -> ('A', False)."""
    if codigo == "SIN DISTINTIVO":
        return "A", False
    return {"0": "CERO", "E": "ECO", "C": "C", "B": "B"}[codigo[3]], codigo[2] == "M"


def buscar_matricula(matricula):
    with closing(sqlite3.connect(f"file:{DB}?mode=ro", uri=True)) as con:
        fila = con.execute("SELECT etiqueta FROM v WHERE matricula = ?", (matricula,)).fetchone()
    return traducir(CODIGOS[fila[0]]) if fila else None


def regla(zona, etiqueta, padron, hoy):
    """La única regla vigente hoy para esa combinación (test_demo.py comprueba que siempre hay una)."""
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


def consulta_geocodificador(direccion):
    """CartoCiudad se equivoca de portal con el código postal («Calle Alcalá 30, 28014» -> Alcalá 380): se quita.
    Y se añade «Madrid» si no está, para no acabar en la Calle Mayor de otro municipio."""
    sin_cp = " ".join(re.sub(r"\b28\d{3}\b", " ", direccion).split())
    sin_cp = re.sub(r"\s*,(\s*,)*\s*", ", ", sin_cp).strip(" ,")
    return sin_cp if "madrid" in sin_cp.lower() else f"{sin_cp}, Madrid"


@lru_cache(maxsize=1024)
def geocodificar(direccion):
    r = httpx.get(CARTOCIUDAD, params={"q": consulta_geocodificador(direccion)}, timeout=5)
    r.raise_for_status()
    datos = r.json() if r.content.strip() else None
    return datos if datos and datos.get("lat") is not None else None


MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


def titulo(texto):
    """CartoCiudad devuelve las calles en mayúsculas: «CALLE DE LA PAZ» -> «Calle de la Paz»."""
    palabras = texto.lower().split()
    return " ".join(p if i and p in MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def texto_direccion(d):
    calle = " ".join(str(d[k]) for k in ("tip_via", "address", "portalNumber") if d.get(k))
    return f"{titulo(calle)}, {d.get('postalCode') or ''} {d.get('poblacion') or ''}".strip(" ,")


# Sacadas del propio fichero de la DGT (38,7 M matrículas): letras del formato actual y códigos de provincia antiguos.
CONSONANTES = set("BCDFGHJKLMNPRSTVWXYZ")
PROVINCIAS = set("A AB AL AV B BA BI BU C CA CC CE CO CR CS CU GC GI GR GU H HU IB J L LE LO LU M MA ML MU "
                 "NA O OU P PM PO S SA SE SG SO SS T TE TF TO V VA VI Z ZA".split())
FORMATOS = "Las matrículas españolas son 4 números y 3 consonantes (1234 BCD) o, las antiguas, provincia + números + letras (M 1234 AB)"


def validar_matricula(matricula):
    """Aplica las reglas de las matrículas españolas (las del registro de la DGT).
    Devuelve (matrícula normalizada, None) si el formato es correcto, o (None, motivo) si no lo es."""
    m = re.sub(r"[\s.-]", "", matricula.upper())
    if "Ñ" in m:
        return None, "Las matrículas no llevan la letra Ñ."
    if not re.fullmatch(r"[A-Z0-9]+", m):
        return None, "Una matrícula solo lleva letras y números."
    if actual := re.fullmatch(r"[CREH]?\d{4}([A-Z]{3})", m):  # desde 2000; C ciclomotor, R remolque, E especial, H histórico
        vocales = sorted(set(actual.group(1)) - CONSONANTES - {"Q"})
        if vocales:
            return None, f"Las matrículas actuales no llevan vocales ({', '.join(vocales)}): son 4 números y 3 consonantes, como 1234 BCD."
        if "Q" in actual.group(1):
            return None, "Las matrículas actuales no llevan la letra Q: son 4 números y 3 consonantes, como 1234 BCD."
        return m, None
    if antigua := re.fullmatch(r"([A-Z]{1,2})(\d{4}[A-Z]{1,2}|\d{1,6})", m):  # provincial (1971-2000) o numérica (antes de 1971)
        provincia, resto = antigua.groups()
        if provincia not in PROVINCIAS:
            return None, f"«{provincia}» no es un código de provincia de las matrículas antiguas (M, B, MA, SE…)."
        if "Q" in resto:
            return None, "Las matrículas antiguas no llevan la letra Q."
        return (provincia + resto.zfill(6) if resto.isdigit() else m), None  # el fichero guarda las numéricas con 6 cifras
    return None, f"{FORMATOS}. Si tu coche tiene matrícula extranjera, identifícalo «Por etiqueta»."


@lru_cache(maxsize=1024)
def sugerir(texto):
    """Direcciones de Madrid que empiezan como lo escrito: «mayor 10» -> («Calle Mayor 10, 28013 Madrid», …)."""
    r = httpx.get(CARTOCIUDAD_CANDIDATOS, timeout=5, params={
        "q": texto, "limit": 6, "municipio_filter": "Madrid",
        "no_process": "municipio,poblacion,toponimo,expendeduria,ngbe",  # solo calles y portales
    })
    r.raise_for_status()
    sugerencias = []
    for c in r.json():
        calle = titulo(c.get("address", "").split(",")[0])  # «CALLE MAYOR 10, Madrid» -> «Calle Mayor 10»
        sugerencia = f"{calle}, Madrid"  # sin código postal: confunde al geocodificador
        if calle and sugerencia not in sugerencias:
            sugerencias.append(sugerencia)
    return tuple(sugerencias)


class Busqueda(BaseModel):
    texto: str = Field(min_length=3, max_length=200)


class Consulta(BaseModel):
    direccion: str = Field(min_length=1, max_length=200)
    padron: Padron
    etiqueta: Etiqueta | None = None  # por etiqueta (la pegatina)...
    matricula: str | None = Field(default=None, max_length=20)  # ...o por matrícula: exactamente uno de los dos

    @model_validator(mode="after")
    def etiqueta_o_matricula(self):
        if bool(self.etiqueta) == bool((self.matricula or "").strip()):
            raise ValueError("hace falta la etiqueta o la matrícula, pero no las dos")
        return self


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    # OSM exige Referer en las teselas: se envía solo el origen, nunca la ruta.
    respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.post("/api/comprobar")
def comprobar(c: Consulta):
    etiqueta, origen = c.etiqueta, "elegida"
    if (c.matricula or "").strip():
        matricula, motivo = validar_matricula(c.matricula)
        if motivo:
            return {"estado": "matricula_no_valida", "motivo": motivo}
        if re.fullmatch(r"H\d{4}[A-Z]{3}", matricula):
            # Las matrículas históricas no están en el fichero de distintivos: el formato ya dice que es histórico.
            etiqueta, origen = "H", "matricula_historica"
        else:
            encontrada = buscar_matricula(matricula)
            if not encontrada:
                return {"estado": "matricula_no_encontrada"}
            etiqueta, es_moto = encontrada
            origen = "dgt"
            if es_moto:
                return {"estado": "moto"}

    try:
        lugar = geocodificar(" ".join(c.direccion.split()))
    except httpx.HTTPError:
        return {"estado": "servicio_no_disponible"}
    if not lugar:
        return {"estado": "direccion_no_encontrada"}
    destino = {"direccion": texto_direccion(lugar), "lat": lugar["lat"], "lng": lugar["lng"]}
    resultado = veredicto(lugar["lng"], lugar["lat"], etiqueta, c.padron, date.today())
    if lugar.get("muniCode") != MUNICIPIO_MADRID or not resultado:
        return {"estado": "fuera_de_madrid", "destino": destino}

    r, zona = resultado
    nota = None
    if origen == "dgt" and etiqueta == "A" and r["veredicto"] == "no_puede":
        # Un histórico con su matrícula original sale como «sin etiqueta» en el fichero de la DGT.
        nota = "Si tu coche lleva la pegatina H de vehículo histórico, compruébalo «Por etiqueta» eligiendo «Histórico»."
    return {
        "estado": "ok",
        "veredicto": r["veredicto"],
        "etiqueta": etiqueta,
        "etiqueta_origen": origen,
        "zona": {"id": zona, "nombre": ZONAS[zona][0]},
        "motivo": r["motivo"],
        "fuente": {**REGLAS["norma"], "articulo": r["articulo"]},
        "destino": destino,
        "nota": nota,
    }


# POST y no GET: lo que escribe el usuario no debe acabar en el registro de accesos (va en el cuerpo).
@app.post("/api/direcciones")
def direcciones(b: Busqueda):
    try:
        return {"sugerencias": list(sugerir(" ".join(b.texto.lower().split())))}
    except httpx.HTTPError:
        return {"sugerencias": []}  # sin sugerencias se puede seguir escribiendo la dirección a mano


@app.get("/api/zonas")
def zonas(padron: Padron = "fuera", etiqueta: Etiqueta | None = None):
    hoy = date.today()
    features = []
    for f in ZONAS_GEOJSON["features"]:
        props = dict(f["properties"])
        props["veredicto"] = regla(props["id"], etiqueta, padron, hoy)["veredicto"] if etiqueta else None
        features.append({**f, "properties": props})
    return {"type": "FeatureCollection", "features": features}


app.mount("/", StaticFiles(directory=os.path.join(AQUI, "static"), html=True), name="static")
