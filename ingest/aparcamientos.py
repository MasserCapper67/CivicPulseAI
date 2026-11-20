"""Genera data/aparcamientos.json: parkings del servicio SOAP del Ayuntamiento con sus tarifas.

Uso: .venv/bin/python -m ingest.aparcamientos   (≈ 1 min: una petición cada 0,5 s)
"""
import json
import os
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from app.externos import N, SOAP_PARKINGS, pedir_lista_parkings
from app.vehiculo import RAIZ
from ingest import registrar_fuente

SALIDA = RAIZ / "data" / "aparcamientos.json"
PAUSA = 0.5  # s entre peticiones: los servidores del Ayuntamiento cortan las ráfagas
MIN_PARKINGS = 50


def _sin_tildes(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def leer_tarifas(xml):
    """Tramos de precio de un GetDetailParking: por minuto (progresivos) y máximo diario."""
    tarifas = []
    for t in ET.fromstring(xml).iter(N + "rates"):
        periodo = _sin_tildes(t.findtext(N + "periodPricing") or "")
        # shortcut: «TARIFA ACCESO» tiene semántica desconocida y se ignora; revisar si aparece en parkings relevantes
        if periodo not in ("minutos", "maximo") or "ACCESO" in (t.findtext(N + "description") or "").upper():
            continue
        tarifas.append({"desde": int(t.findtext(N + "minutesStayInitation")), "hasta": int(t.findtext(N + "minutesStayEnd")),
                        "periodo": periodo, "precio": float(t.findtext(N + "rate"))})
    return sorted(tarifas, key=lambda t: t["desde"])


def pedir_detalle(id_parking, familia):
    cuerpo = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/" '
              'xmlns:inf="http://schemas.datacontract.org/2004/07/InfoParking"><soapenv:Body><tem:GetDetailParking>'
              f"<tem:parametersDetailParking><inf:date>{datetime.now().isoformat(timespec='seconds')}</inf:date>"
              f"<inf:family>{familia}</inf:family><inf:id>{id_parking}</inf:id><inf:language>ES</inf:language>"
              "<inf:publicData>true</inf:publicData></tem:parametersDetailParking></tem:GetDetailParking></soapenv:Body></soapenv:Envelope>")
    r = httpx.post(SOAP_PARKINGS, content=cuerpo, timeout=10, headers={
        "Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/iInfoParking/GetDetailParking"'})
    r.raise_for_status()
    return r.content


def main():
    lista = ET.fromstring(pedir_lista_parkings())
    parkings, sin_tarifas = [], 0
    for p in lista.iter(N + "lstParking"):
        time.sleep(PAUSA)
        try:
            tarifas = leer_tarifas(pedir_detalle(p.findtext(N + "id"), p.findtext(N + "familyCode")))
        except (httpx.HTTPError, ET.ParseError):
            tarifas = []  # sin tarifas el parking sigue siendo una alternativa, con precio «no disponible»
        sin_tarifas += not tarifas
        parkings.append({"id": int(p.findtext(N + "id")), "nombre": p.findtext(N + "name").strip(),
                         "direccion": (p.findtext(N + "address") or "").strip(),
                         "lat": float(p.findtext(N + "latitude")), "lng": float(p.findtext(N + "longitude")),
                         "tarifas": tarifas})
    assert len(parkings) >= MIN_PARKINGS, f"demasiado pocos parkings: {len(parkings)}"
    tmp = SALIDA.with_suffix(".tmp")
    tmp.write_text(json.dumps(parkings, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, SALIDA)  # de golpe: si algo falla antes, el fichero anterior queda intacto
    registrar_fuente("aparcamientos", SOAP_PARKINGS, datetime.now().date().isoformat())
    print(f"ok: {len(parkings)} parkings, {len(parkings) - sin_tarifas} con tarifas")


if __name__ == "__main__":
    main()
