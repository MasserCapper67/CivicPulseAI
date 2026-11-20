"""Alternativas cuando no se puede entrar: dónde dejar el coche, cuánto se tarda desde allí y cuánto cuesta."""
import json
import math

import shapely
from shapely.ops import nearest_points

from app.geo import RAIZ, TERMINO, ZONAS, a_grados, a_metros, distancia_m, zonas_en
from app.reglas import regla, veredicto

# shortcut: sin motor de rutas; distancia en línea recta × rodeo. Mejorar con un servicio de rutas si da tiempo.
A_PIE_KMH = 4.5
RODEO = 1.3                # de línea recta a recorrido por calles
MAX_A_PIE_KM = 1.5         # más lejos, transporte público
TRANSPORTE_KMH = 25
ESPERA_Y_ANDAR_MIN = 10    # 5 de espera + 5 andando hasta y desde la estación
BILLETE_ZONA_A = 2.00      # Metro zona A, sencillo de 10 o más estaciones (CRTM, consultado el 19/11/2026)
BILLETE_COMBINADO = 3.00   # billete combinado Metro, fuera de la zona A (CRTM, consultado el 19/11/2026)
DESPLAZAMIENTOS_M = (30, 100, 300)  # el punto permitido se aparta del borde; más si cae en un entrante
RADIO_PARADAS_M = 600
MAX_PARADAS = 3
MAX_POR_TIPO = 2
MAX_ALTERNATIVAS = 5


def _cargar(nombre):
    ruta = RAIZ / "data" / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []


APARCAMIENTOS = _cargar("aparcamientos.json")
ESTACIONES = _cargar("estaciones.json")


def coste_parking(tarifas, minutos):
    """Tramos por minuto sumados de forma progresiva; el máximo es tope diario y, desde su minuto de inicio, precio fijo."""
    por_minuto = [t for t in tarifas if t["periodo"] == "minutos"]
    if not por_minuto:
        return None
    maximo = next((t for t in tarifas if t["periodo"] == "maximo"), None)
    if maximo and minutos >= maximo["desde"]:
        return maximo["precio"]
    total = sum(max(0, min(minutos, t["hasta"]) - max(t["desde"] - 1, 0)) * t["precio"] for t in por_minuto)
    return round(min(total, maximo["precio"]) if maximo else total, 2)


def minutos_hasta(lng, lat, destino_lng, destino_lat):
    km = distancia_m(lng, lat, destino_lng, destino_lat) * RODEO / 1000
    if km <= MAX_A_PIE_KM:
        return max(1, round(km / A_PIE_KMH * 60)), "a pie"
    return round(km / TRANSPORTE_KMH * 60 + ESPERA_Y_ANDAR_MIN), "en transporte público"


def punto_permitido(lng, lat, zona):
    """El punto fuera de la zona más cercano al destino. La ZBE general son 45 trozos separados por corredores
    de autovía (donde no se deja el coche): para ella cuenta el borde del término municipal."""
    zona_m = a_metros(TERMINO if zona == "zbe_madrid" else ZONAS[zona][1])
    exterior = shapely.union_all([shapely.Polygon(p.exterior) for p in shapely.get_parts(zona_m)])
    destino = a_metros(shapely.Point(lng, lat))
    borde = nearest_points(exterior.boundary, destino)[0]
    dx, dy = borde.x - destino.x, borde.y - destino.y
    d = math.hypot(dx, dy) or 1.0
    for metros in DESPLAZAMIENTOS_M:
        fuera = shapely.Point(borde.x + dx / d * metros, borde.y + dy / d * metros)
        if not exterior.contains(fuera):
            p = a_grados(fuera)
            return p.x, p.y
    return None


def paradas_cercanas(lng, lat):
    cerca = sorted(((distancia_m(e["lng"], e["lat"], lng, lat), e) for e in ESTACIONES), key=lambda de: de[0])
    return [{"nombre": e["nombre"], "modo": e["modo"], "lineas": e["lineas"], "metros": round(d)}
            for d, e in cerca[:MAX_PARADAS] if d <= RADIO_PARADAS_M]


def enlace_maps(lat, lng):
    """Ruta en coche de Google Maps hasta el punto (el origen lo pone Google: la ubicación del usuario)."""
    return f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lng:.6f}&travelmode=driving"


def _permitido(lng, lat, etiqueta, padron, hoy, validos):
    v = veredicto(lng, lat, etiqueta, padron, hoy)
    return v is None or v[0]["veredicto"] in validos


def _alternativa(tipo, nombre, lng, lat, destino, coste_eur=None, plazas_libres=None):
    minutos, como = minutos_hasta(lng, lat, destino["lng"], destino["lat"])
    return {"tipo": tipo, "nombre": nombre, "lat": lat, "lng": lng, "minutos": minutos, "como": como,
            "coste_eur": coste_eur, "coste_desde": False, "plazas_libres": plazas_libres, "mas_barata": False,
            "como_llegar": enlace_maps(lat, lng)}


def _zona_que_prohibe(destino, etiqueta, padron, hoy):
    """La zona más amplia que no deja circular libremente (en zonas.geojson van de la más amplia a la más
    específica). No es la del veredicto: aquel cita la más específica para que el mensaje sea claro."""
    for zona in zonas_en(destino["lng"], destino["lat"]):
        if regla(zona, etiqueta, padron, hoy)["veredicto"] != "puede":
            return zona
    return None


def alternativas(destino, etiqueta, padron, horas, hoy, plazas):
    """Hasta 2 parkings, 2 estaciones y el punto permitido más cercano, ordenados por minutos desde que se aparca."""
    parkings = [
        _alternativa("parking", f"Aparcamiento {p['nombre']}", p["lng"], p["lat"], destino,
                     coste_eur=coste_parking(p["tarifas"], horas * 60), plazas_libres=plazas.get(p["id"]))
        for p in APARCAMIENTOS
        if plazas.get(p["id"]) != 0 and _permitido(p["lng"], p["lat"], etiqueta, padron, hoy, ("puede", "solo_parking"))
    ]
    estaciones = []
    for e in ESTACIONES:
        if not _permitido(e["lng"], e["lat"], etiqueta, padron, hoy, ("puede",)):
            continue
        alternativa = _alternativa("estacion", f"{e['modo']} {e['nombre']} ({', '.join(e['lineas'])})", e["lng"], e["lat"], destino)
        if e["modo"] == "Metro" and alternativa["como"] == "en transporte público":
            alternativa["coste_eur"] = 2 * (BILLETE_ZONA_A if e["corona"] == "A" else BILLETE_COMBINADO)  # ida y vuelta
            alternativa["coste_desde"] = True  # no incluye aparcar en la calle
        estaciones.append(alternativa)

    por_minutos = lambda a: a["minutos"]  # noqa: E731
    elegidas = sorted(parkings, key=por_minutos)[:MAX_POR_TIPO] + sorted(estaciones, key=por_minutos)[:MAX_POR_TIPO]
    zona = _zona_que_prohibe(destino, etiqueta, padron, hoy)
    punto = punto_permitido(destino["lng"], destino["lat"], zona) if zona else None
    if punto and _permitido(*punto, etiqueta, padron, hoy, ("puede",)):
        elegidas.append(_alternativa("punto_permitido", f"Fuera de {ZONAS[zona][0]}", *punto, destino))
    elegidas = sorted(elegidas, key=por_minutos)[:MAX_ALTERNATIVAS]

    completas = [a for a in elegidas if a["coste_eur"] is not None and not a["coste_desde"]]
    if completas:
        min(completas, key=lambda a: a["coste_eur"])["mas_barata"] = True
    return elegidas
