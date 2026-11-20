"""Servicios de terceros: CartoCiudad (direcciones) y el servicio SOAP de parkings del Ayuntamiento (plazas libres)."""
import re
import time
import xml.etree.ElementTree as ET
from functools import lru_cache

import httpx

CARTOCIUDAD = "https://www.cartociudad.es/geocoder/api/geocoder/find"
CARTOCIUDAD_CANDIDATOS = "https://www.cartociudad.es/geocoder/api/geocoder/candidates"
SOAP_PARKINGS = "https://servayto.madrid.es/MTPAR_WSINFO/InfoParking"
N = "{http://schemas.datacontract.org/2004/07/InfoParking}"  # espacio de nombres de las respuestas SOAP
CADUCIDAD_OCUPACION = 300  # s: los servidores del Ayuntamiento cortan las ráfagas de peticiones
CADUCIDAD_FALLO = 60       # s: con el servicio caído tampoco se insiste en cada petición
MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


def titulo(texto):
    """CartoCiudad devuelve las calles en mayúsculas: «CALLE DE LA PAZ» -> «Calle de la Paz»."""
    palabras = texto.lower().split()
    return " ".join(p if i and p in MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def texto_direccion(d):
    calle = " ".join(str(d[k]) for k in ("tip_via", "address", "portalNumber") if d.get(k))
    return f"{titulo(calle)}, {d.get('postalCode') or ''} {d.get('poblacion') or ''}".strip(" ,")


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


@lru_cache(maxsize=1024)
def sugerir(texto):
    """Direcciones de Madrid que empiezan como lo escrito: «mayor 10» -> («Calle Mayor 10, Madrid», …)."""
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


def pedir_lista_parkings():
    """GetListParking: todos los parkings con coordenadas y, los que la publican, su ocupación. Lanza httpx.HTTPError."""
    cuerpo = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">'
              "<soapenv:Body><tem:GetListParking><tem:language>ES</tem:language></tem:GetListParking></soapenv:Body>"
              "</soapenv:Envelope>")
    r = httpx.post(SOAP_PARKINGS, content=cuerpo, timeout=5, headers={
        "Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/iInfoParking/GetListParking"'})
    r.raise_for_status()
    return r.content


def leer_ocupacion(xml):
    """id del parking -> plazas libres, solo de los que traen el dato."""
    plazas = {}
    for parking in ET.fromstring(xml).iter(N + "lstParking"):
        try:
            plazas[int(parking.findtext(N + "id"))] = int(parking.findtext(f"{N}lstOccupation/{N}occupation/{N}free"))
        except (TypeError, ValueError):
            continue  # sin dato o mal formado: ese parking queda «sin datos de ocupación»
    return plazas


_cache_ocupacion = None  # (caduca_en, plazas)


def ocupacion():
    """Plazas libres en tiempo real (caché de 5 min). Si el servicio falla, {} durante 1 min: la app sigue sin ese dato."""
    global _cache_ocupacion
    if _cache_ocupacion and time.monotonic() < _cache_ocupacion[0]:
        return _cache_ocupacion[1]
    try:
        plazas, caducidad = leer_ocupacion(pedir_lista_parkings()), CADUCIDAD_OCUPACION
    except (httpx.HTTPError, ET.ParseError):
        plazas, caducidad = {}, CADUCIDAD_FALLO
    _cache_ocupacion = (time.monotonic() + caducidad, plazas)
    return plazas
