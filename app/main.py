"""¿Puedo entrar con mi coche? — API y frontend.

Arranque: .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
import re
from datetime import date
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from app import externos
from app.geo import RAIZ, ZONAS, ZONAS_GEOJSON
from app.ranking import APARCAMIENTOS, alternativas, coste_parking, enlace_maps, paradas_cercanas
from app.reglas import REGLAS, regla, veredicto
from app.vehiculo import buscar_matricula, validar_matricula

MUNICIPIO_MADRID = "28079"
Etiqueta = Literal["CERO", "ECO", "C", "B", "A", "H"]  # H = vehículo histórico (pegatina H)
Padron = Literal["fuera", "madrid", "centro"]


class Busqueda(BaseModel):
    texto: str = Field(min_length=3, max_length=200)


class Consulta(BaseModel):
    direccion: str = Field(min_length=1, max_length=200)
    padron: Padron
    etiqueta: Etiqueta | None = None  # por etiqueta (la pegatina)...
    matricula: str | None = Field(default=None, max_length=20)  # ...o por matrícula: exactamente uno de los dos
    horas: int = Field(2, ge=1, le=24)  # estancia para calcular el coste de los parkings

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
        lugar = externos.geocodificar(" ".join(c.direccion.split()))
    except httpx.HTTPError:
        return {"estado": "servicio_no_disponible"}
    if not lugar:
        return {"estado": "direccion_no_encontrada"}
    destino = {"direccion": externos.texto_direccion(lugar), "lat": lugar["lat"], "lng": lugar["lng"]}
    hoy = date.today()
    resultado = veredicto(lugar["lng"], lugar["lat"], etiqueta, c.padron, hoy)
    if lugar.get("muniCode") != MUNICIPIO_MADRID or not resultado:
        return {"estado": "fuera_de_madrid", "destino": destino}

    r, zona = resultado
    nota = None
    if origen == "dgt" and etiqueta == "A" and r["veredicto"] == "no_puede":
        # Un histórico con su matrícula original sale como «sin etiqueta» en el fichero de la DGT.
        nota = "Si tu coche lleva la pegatina H de vehículo histórico, compruébalo «Por etiqueta» eligiendo «Histórico»."
    puede = r["veredicto"] == "puede"
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
        "horas": c.horas,
        "como_llegar": enlace_maps(destino["lat"], destino["lng"]) if puede else None,
        "alternativas": [] if puede else alternativas(destino, etiqueta, c.padron, zona, c.horas, hoy, externos.ocupacion()),
        "paradas_cercanas": paradas_cercanas(destino["lng"], destino["lat"]),
    }


# POST y no GET: lo que escribe el usuario no debe acabar en el registro de accesos (va en el cuerpo).
@app.post("/api/direcciones")
def direcciones(b: Busqueda):
    try:
        return {"sugerencias": list(externos.sugerir(" ".join(b.texto.lower().split())))}
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


@app.get("/api/parkings")
def parkings():
    plazas = externos.ocupacion()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]},
         "properties": {"nombre": p["nombre"], "plazas_libres": plazas.get(p["id"]),
                        "precio_hora": coste_parking(p["tarifas"], 60)}}
        for p in APARCAMIENTOS]}


app.mount("/", StaticFiles(directory=RAIZ / "app" / "static", html=True), name="static")
