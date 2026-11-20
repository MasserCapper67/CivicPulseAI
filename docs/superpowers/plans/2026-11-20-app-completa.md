# CivicPulseAI · Implementación completa — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el prototipo de `demo/` en la app definitiva y añadir lo que falta: alternativas (parkings, estaciones y punto permitido más cercano, con tiempo, coste y duración editable) cuando no se puede entrar, y enlaces de ruta a Google Maps.

**Architecture:** Un solo proceso FastAPI sirve la API JSON y el frontend estático (`app/static`). Los datos locales (`data/`) los generan scripts de ingesta (`ingest/`); en ejecución solo se llama a CartoCiudad (direcciones) y, como mucho una vez cada 5 min, al SOAP de parkings (plazas libres). Módulos por responsabilidad: `vehiculo`, `geo`, `reglas`, `externos`, `ranking`, `main`.

**Tech Stack:** Python ≥ 3.12 · FastAPI 0.165.0 · uvicorn 0.54.0 · Shapely 2.2.0 · httpx 0.28.1 · pytest 9.2.0 · HTML/CSS/JS sin build · Leaflet 1.9.4 y Barlow vendorizados · `ogr2ogr` (GDAL) solo en la ingesta.

**Spec:** [`docs/superpowers/specs/2026-11-19-zbe-madrid-design.md`](../specs/2026-11-19-zbe-madrid-design.md). Punto de partida: el prototipo `demo/` (validado con el equipo); se reutiliza su código y se borra al final.

## Global Constraints

- Dependencias de ejecución: solo `fastapi`, `uvicorn`, `shapely`, `httpx`, con versión fijada; `pytest` solo para pruebas. Nada de librerías GIS ni SOAP en Python.
- Regla de `CLAUDE.md`: una única respuesta clara; nada que el usuario tenga que interpretar.
- Interfaz en español. Todo texto externo o del usuario se pinta con `textContent` / nodos DOM, nunca `innerHTML`.
- Seguridad (spec 9.1): Pydantic en la frontera; SQLite `file:…?mode=ro` con consultas parametrizadas; URLs externas fijas y `timeout=5`; cabeceras `Content-Security-Policy: default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`; `Cache-Control: no-store` en `/api/*`; `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`; uvicorn en `127.0.0.1`.
- Privacidad: lo que escribe el usuario viaja por POST (nunca en la URL) y no se guarda ni se registra.
- Los servidores del Ayuntamiento cortan las ráfagas: la ingesta espera ≥ 0,5 s entre peticiones a `datos.madrid.es` / `servayto.madrid.es`; en ejecución, como mucho 1 llamada SOAP cada 300 s.
- Reglas provisionales: `data/reglas.json` es el de `demo/data/reglas.json` sin cambios (artículos «PENDIENTE (BOAM)»); el banner amarillo se mantiene.
- Cachés acotadas: `lru_cache(maxsize=1024)` en `geocodificar` y `sugerir`; ocupación de parkings con caducidad de 300 s.
- Rutas relativas a la raíz del repo: `RAIZ = Path(__file__).resolve().parents[1]`.
- Se trabaja en la rama `feat/app-completa`; un commit por tarea.

## Review Focus

1. **Coche sin etiqueta de fuera con destino en Sol:** todos los parkings y estaciones de Madrid están dentro de la ZBE; el «punto permitido» debe quedar fuera del término municipal (borde exterior), no en un hueco de autovía dentro de Madrid. → Task 5, `test_punto_permitido_sin_etiqueta_sale_del_municipio`.
2. **SOAP caído en ejecución:** la comprobación responde igual, con alternativas y sin plazas libres. → Task 3, `test_ocupacion_devuelve_vacio_si_falla`; Task 6, `test_comprobar_sin_ocupacion`.
3. **Parking sin tarifas o coste parcial («desde»):** nunca se marca como «más barata». → Task 5, `test_mas_barata_solo_con_coste_completo`.
4. **Estancias largas:** 700 min y 24 h cuestan el máximo diario, no más. → Task 5, `test_coste_parking_tope_diario`.
5. **Ninguna alternativa posible:** la API devuelve `alternativas: []` y la página dice «No encontramos alternativas cerca de tu destino.». → Task 5, `test_sin_candidatos_devuelve_lista_vacia`; Task 7, paso de comprobación manual.

---

## Estructura de ficheros

```
requirements.txt  pytest.ini  .gitignore
app/
  __init__.py
  vehiculo.py     matrícula → etiqueta (validación española, SQLite)
  geo.py          zonas, proyección a metros, distancias
  reglas.py       regla vigente y veredicto en un punto
  externos.py     CartoCiudad (direcciones) y plazas libres (SOAP)
  ranking.py      alternativas, coste de parkings, paradas cercanas, enlace a Google Maps
  main.py         rutas, cabeceras, estáticos
  static/         index.html · app.js · style.css · img/ · vendor/ · geo/camaras.geojson
ingest/
  __init__.py     registrar_fuente()
  dgt.py  zonas.py  aparcamientos.py  estaciones.py
data/
  reglas.json  zonas.geojson  aparcamientos.json  estaciones.json  fuentes.json   (en git)
  matriculas.db  raw/                                                            (fuera de git)
tests/
  test_vehiculo.py  test_reglas.py  test_externos.py  test_ingest.py  test_ranking.py  test_api.py
  fixtures/lista_parkings.xml  fixtures/detalle_parking.xml
```

---

### Task 1: Esqueleto del proyecto y vehículo

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `app/__init__.py`, `app/vehiculo.py`, `ingest/__init__.py`, `ingest/dgt.py`, `tests/test_vehiculo.py`
- Origen: `demo/app.py` (`traducir`, `buscar_matricula`, `validar_matricula`, `CONSONANTES`, `PROVINCIAS`, `FORMATOS`), `demo/ingest_dgt.py`

**Interfaces:**
- Produces (`app/vehiculo.py`): `RAIZ: Path`, `DB: Path` (= `RAIZ/"data"/"matriculas.db"`), `CODIGOS: list[str]` (orden de `demo/ingest_dgt.py`; el índice es lo guardado en la base), `validar_matricula(texto: str) -> tuple[str | None, str | None]`, `traducir(codigo: str) -> tuple[str, bool]`, `buscar_matricula(matricula: str) -> tuple[str, bool] | None`.
- Produces (`ingest/__init__.py`): `registrar_fuente(nombre: str, url: str, fecha_fichero: str | None) -> None` — actualiza `data/fuentes.json` (`{nombre: {"url", "fecha_fichero", "descargado": date.today().isoformat()}}`).
- `ingest/dgt.py` importa `CODIGOS` y `DB` de `app.vehiculo`, guarda el ZIP en `data/raw/` y llama a `registrar_fuente("dgt", URL, last_modified)`.

- [ ] **Step 0: Rama y entorno**

```bash
git switch -c feat/app-completa
uv venv && uv pip install fastapi==0.165.0 uvicorn==0.54.0 shapely==2.2.0 httpx==0.28.1 pytest==9.2.0
mkdir -p data/raw && mv demo/data/matriculas.db data/ && mv demo/data/raw/* data/raw/   # evita volver a descargar
```
`requirements.txt` con esas 5 líneas; `pytest.ini`: `[pytest]` / `pythonpath = .` / `testpaths = tests`; `.gitignore`: `.venv/`, `__pycache__/`, `data/raw/`, `data/*.db`, `data/*.tmp`.

- [ ] **Step 1: Tests** — `tests/test_vehiculo.py`: pasar a funciones pytest las aserciones de `demo/test_demo.py` líneas 18–21 (`traducir`) y 41–51 (`validar_matricula`, incluidos los 8 formatos reales, `H 1234 BCD`, `H 1234 AB`, `M 12345` y los 7 casos inválidos con su pista), más:

```python
@pytest.mark.skipif(not DB.exists(), reason="sin data/matriculas.db: ejecutar python -m ingest.dgt")
def test_buscar_matricula_real():
    assert buscar_matricula("0001CVG") == ("B", False)
    assert buscar_matricula("0003HLN") == ("C", True)
    assert buscar_matricula("9999ZZZ") is None
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_vehiculo.py -v` → FAIL (`app.vehiculo` no existe).
- [ ] **Step 3:** Crear `app/vehiculo.py` moviendo las funciones de `demo/app.py` sin cambiar su comportamiento; crear `ingest/dgt.py` desde `demo/ingest_dgt.py` con las rutas nuevas y `registrar_fuente`.
- [ ] **Step 4:** `.venv/bin/pytest tests/test_vehiculo.py -v` → PASS (4 o más tests, ninguno saltado).
- [ ] **Step 5:** `git add requirements.txt pytest.ini .gitignore app ingest tests && git commit -m "feat: estructura del proyecto y consulta de matrículas"`

---

### Task 2: Zonas, reglas y veredicto

**Files:**
- Create: `app/geo.py`, `app/reglas.py`, `ingest/zonas.py`, `data/reglas.json` (copia literal de `demo/data/reglas.json`), `tests/test_reglas.py`
- Generados: `data/zonas.geojson`, `app/static/geo/camaras.geojson`
- Origen: `demo/ingest_zonas.py`, `demo/app.py` (`regla`, `veredicto`, `GRAVEDAD`)

**Interfaces:**
- Produces (`app/geo.py`): `ZONAS_GEOJSON: dict`; `ZONAS: dict[str, tuple[str, BaseGeometry]]` (id → nombre y geometría preparada, en el orden del fichero: `zbe_madrid`, `zbedep_centro`, `zbedep_eliptica`); `zonas_en(lng: float, lat: float) -> list[str]`; `a_metros(g) -> BaseGeometry` y `a_grados(g) -> BaseGeometry` (escala local: x = lng · cos(40,42°) · 111 320, y = lat · 110 574, con `shapely.transform`); `distancia_m(lng1, lat1, lng2, lat2) -> float`.
- Produces (`app/reglas.py`): `REGLAS: dict`; `regla(zona: str, etiqueta: str, padron: str, hoy: date) -> dict`; `veredicto(lng: float, lat: float, etiqueta: str, padron: str, hoy: date) -> tuple[dict, str] | None` (gana la más restrictiva; si empatan, la más específica = la última en el fichero; `None` fuera de toda zona).
- `ingest/zonas.py` = `demo/ingest_zonas.py` con `RAW = RAIZ/"data/raw/madrid"`, salidas en `data/zonas.geojson` y `app/static/geo/camaras.geojson`, y `registrar_fuente` por cada fichero descargado.

- [ ] **Step 1: Tests** — `tests/test_reglas.py`: la comprobación de completitud de `demo/test_demo.py` líneas 11–16 y los 11 veredictos de las líneas 29–39 (mismos puntos `SOL`, `ELIPTICA`, `RETIRO`, `GETAFE` y fechas), más `assert zonas_en(*SOL) == ["zbe_madrid", "zbedep_centro"]` y `assert 1500 < distancia_m(*SOL, *RETIRO) < 1800`.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_reglas.py -v` → FAIL.
- [ ] **Step 3:** `git mv demo/static app/static` (el frontend del prototipo pasa a ser el definitivo); implementar `app/geo.py` y `app/reglas.py` moviendo el código del prototipo; `ingest/zonas.py`; ejecutar `.venv/bin/python -m ingest.zonas` (usa los ZIP ya presentes en `data/raw/madrid`) → «ok: 3 zonas, 603 cámaras».
- [ ] **Step 4:** `.venv/bin/pytest tests/test_reglas.py -v` → PASS.
- [ ] **Step 5:** `git add app data/reglas.json data/zonas.geojson data/fuentes.json ingest tests demo && git commit -m "feat: zonas oficiales, reglas y veredicto"`

---

### Task 3: Servicios externos (direcciones y plazas libres)

**Files:**
- Create: `app/externos.py`, `tests/test_externos.py`, `tests/fixtures/lista_parkings.xml`
- Origen: `demo/app.py` (`titulo`, `texto_direccion`, `consulta_geocodificador`, `geocodificar`, `sugerir`)

**Interfaces:**
- Produces: `titulo(texto: str) -> str`; `texto_direccion(d: dict) -> str`; `consulta_geocodificador(direccion: str) -> str`; `geocodificar(direccion: str) -> dict | None` (lanza `httpx.HTTPError`); `sugerir(texto: str) -> tuple[str, ...]`; `leer_ocupacion(xml: bytes) -> dict[int, int]` (id → plazas libres; solo los que traen dato); `ocupacion() -> dict[int, int]` (caché 300 s; ante `httpx.HTTPError` o XML inválido devuelve `{}` y **no** cachea el fallo).
- SOAP: `POST https://servayto.madrid.es/MTPAR_WSINFO/InfoParking`, cabeceras `Content-Type: text/xml; charset=utf-8` y `SOAPAction: "http://tempuri.org/iInfoParking/GetListParking"`, cuerpo `<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/"><soapenv:Body><tem:GetListParking><tem:language>ES</tem:language></tem:GetListParking></soapenv:Body></soapenv:Envelope>`. Espacio de nombres de la respuesta: `N = "{http://schemas.datacontract.org/2004/07/InfoParking}"`; cada `N+lstParking` trae `N+id` y, si hay dato, `N+lstOccupation/N+occupation/N+free`. Leer con `xml.etree.ElementTree`.
- Fixture `lista_parkings.xml`: respuesta SOAP mínima con dos `lstParking`: id 3 sin ocupación e id 5 con `<ns2:free>181</ns2:free>`. Antes de dar la tarea por buena, comparar su estructura con una respuesta real (una sola llamada).

- [ ] **Step 1: Tests**

```python
def test_titulo_y_consulta():                       # casos de demo/test_demo.py líneas 61-67
    assert consulta_geocodificador("Calle Alcala 30, 28014 Madrid") == "Calle Alcala 30, Madrid"
    assert titulo("PLAZA DEL CALLAO") == "Plaza del Callao"

def test_leer_ocupacion():
    assert leer_ocupacion((FIXTURES / "lista_parkings.xml").read_bytes()) == {5: 181}

def test_ocupacion_devuelve_vacio_si_falla(monkeypatch):
    def caido(*a, **k): raise httpx.ConnectError("caído")
    monkeypatch.setattr(externos.httpx, "post", caido)
    assert externos.ocupacion() == {}
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_externos.py -v` → FAIL.
- [ ] **Step 3:** Implementar `app/externos.py` (lo del prototipo se mueve tal cual; añadir `leer_ocupacion` y `ocupacion`).
- [ ] **Step 4:** `.venv/bin/pytest tests/test_externos.py -v` → PASS; y una llamada real: `.venv/bin/python -c "from app.externos import ocupacion; print(len(ocupacion()))"` → un número entre 1 y 75.
- [ ] **Step 5:** `git add app tests && git commit -m "feat: direcciones de CartoCiudad y plazas libres de parkings"`

---

### Task 4: Ingesta de parkings y estaciones

**Files:**
- Create: `ingest/aparcamientos.py`, `ingest/estaciones.py`, `tests/test_ingest.py`, `tests/fixtures/detalle_parking.xml`
- Generados (en git): `data/aparcamientos.json`, `data/estaciones.json`

**Interfaces:**
- Produces (`ingest/aparcamientos.py`): `leer_tarifas(xml: bytes) -> list[dict]` → `[{"desde": int, "hasta": int, "periodo": "minutos" | "maximo", "precio": float}]` ordenadas por `desde`; `periodPricing` normalizado sin mayúsculas ni tildes; se descartan otros periodos y los tramos cuya `description` contenga `ACCESO` (*shortcut: semántica desconocida; revisar si aparece en parkings relevantes*).
- `data/aparcamientos.json`: lista de `{"id": int, "nombre": str, "direccion": str, "lat": float, "lng": float, "tarifas": list}`. Proceso: `GetListParking` (Task 3) → por cada parking, espera 0,5 s y `GetDetailParking` con `SOAPAction: "http://tempuri.org/iInfoParking/GetDetailParking"` y cuerpo `<tem:GetDetailParking><tem:parametersDetailParking>` con `inf:date` (ahora, ISO), `inf:family` (= `familyCode` de la lista), `inf:id`, `inf:language` = `ES`, `inf:publicData` = `true` (`xmlns:inf="http://schemas.datacontract.org/2004/07/InfoParking"`). Si un detalle falla: `tarifas: []` y sigue. Valida ≥ 50 parkings antes de escribir (fichero temporal + `os.replace`).
- Produces (`ingest/estaciones.py`): `leer_estaciones(geojson: dict, modo: str) -> list[dict]` → `{"nombre": titulo(DENOMINACION), "modo": "Metro" | "Cercanías", "lineas": list[str], "corona": str | None, "lat": float, "lng": float}`. `LINEAS` viene separado por `", "`; en Metro se antepone `L` («L1»); las estaciones repetidas (mismo nombre y modo) se funden en una con la unión de líneas. Fuentes: `https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/0/query?where=1%3D1&outFields=DENOMINACION,LINEAS,CORONATARIFARIA&outSR=4326&f=geojson` (Metro, 293 registros) y lo mismo con `M5_Red` (Cercanías, 111). Salida: `data/estaciones.json`.
- Ambas llaman a `registrar_fuente`.

- [ ] **Step 1: Tests**

```python
TARIFAS_RECUERDO = [
    {"desde": 0, "hasta": 30, "periodo": "minutos", "precio": 0.0409},
    {"desde": 31, "hasta": 90, "periodo": "minutos", "precio": 0.0366},
    {"desde": 91, "hasta": 660, "periodo": "minutos", "precio": 0.0489},
    {"desde": 661, "hasta": 1440, "periodo": "maximo", "precio": 31.25},
]

def test_leer_tarifas():  # el fixture trae esos 4 tramos («MINUTOS» en mayúsculas en uno) + un «TARIFA ACCESO»
    assert leer_tarifas((FIXTURES / "detalle_parking.xml").read_bytes()) == TARIFAS_RECUERDO

def test_leer_estaciones_funde_repetidas():
    fc = {"features": [punto("SOL", "1, 2, 3", "A", -3.70326, 40.41687), punto("SOL", "1, 2, 3", "A", -3.70326, 40.41684)]}
    assert leer_estaciones(fc, "Metro") == [{"nombre": "Sol", "modo": "Metro", "lineas": ["L1", "L2", "L3"],
                                              "corona": "A", "lat": 40.41687, "lng": -3.70326}]
```
(`punto` es un ayudante del test que construye una feature GeoJSON con `DENOMINACION`, `LINEAS` y `CORONATARIFARIA`.)

- [ ] **Step 2:** `.venv/bin/pytest tests/test_ingest.py -v` → FAIL.
- [ ] **Step 3:** Implementar ambos scripts; ejecutar `.venv/bin/python -m ingest.aparcamientos` (≈ 1 min) y `.venv/bin/python -m ingest.estaciones`.
- [ ] **Step 4:** `.venv/bin/pytest tests/test_ingest.py -v` → PASS; `python -c` que cuente: ≥ 50 parkings y ≥ 35 con tarifas; ≥ 250 estaciones de Metro y ≥ 100 de Cercanías.
- [ ] **Step 5:** `git add ingest tests data/aparcamientos.json data/estaciones.json data/fuentes.json && git commit -m "feat: ingesta de parkings con tarifas y de estaciones"`

---

### Task 5: Alternativas

**Files:**
- Create: `app/ranking.py`, `tests/test_ranking.py`

**Interfaces:**
- Consumes: `geo.ZONAS`, `geo.a_metros`, `geo.a_grados`, `geo.distancia_m`, `reglas.veredicto`, `data/aparcamientos.json`, `data/estaciones.json` (si faltan, listas vacías).
- Produces:
  - `coste_parking(tarifas: list[dict], minutos: int) -> float | None`
  - `minutos_hasta(lng: float, lat: float, destino_lng: float, destino_lat: float) -> tuple[int, str]` → `(minutos, "a pie" | "en transporte público")`
  - `punto_permitido(lng: float, lat: float, zona: str) -> tuple[float, float] | None` → `(lng, lat)`
  - `paradas_cercanas(lng: float, lat: float) -> list[dict]` → `{"nombre", "modo", "lineas", "metros"}`
  - `enlace_maps(lat: float, lng: float) -> str`
  - `alternativas(destino: dict, etiqueta: str, padron: str, zona: str, horas: int, hoy: date, plazas: dict[int, int]) -> list[dict]` → cada una `{"tipo": "parking" | "estacion" | "punto_permitido", "nombre", "lat", "lng", "minutos", "como", "coste_eur", "coste_desde", "plazas_libres", "mas_barata", "como_llegar"}`
- Valores fijos (constantes con nombre y comentario de fuente): a pie 4,5 km/h; rodeo × 1,3; a pie si la distancia con rodeo ≤ 1,5 km; si no, transporte a 25 km/h + 10 min (5 de espera + 5 andando); billete Metro corona A 2,00 € y fuera de ella 3,00 € (billete combinado), por trayecto, × 2 ida y vuelta (CRTM, 19/11/2026); Cercanías y aparcar en la calle: precio desconocido; desplazamiento del punto permitido 30 m; paradas a ≤ 600 m, como mucho 3; como mucho 2 alternativas por tipo y 5 en total.
- Reglas: candidato parking válido si en su posición el veredicto es `None`, `puede` o `solo_parking`, y no está en `plazas` con valor 0; estación y punto permitido, si es `None` o `puede`. Coste: parking → `coste_parking(tarifas, horas * 60)`, `coste_desde = False`; estación de Metro alcanzada «en transporte público» → billete × 2 con `coste_desde = True` (no incluye aparcar en la calle); el resto → `None`. Orden: mejores 2 parkings + mejores 2 estaciones + punto permitido, juntos por minutos, máximo 5. `mas_barata = True` solo en la de menor `coste_eur` entre las que tienen coste conocido y `coste_desde = False` (como mucho una). Nombres: «Aparcamiento X», «Metro X (L1, L2)», «Cercanías X (C-3)», «Fuera de {nombre de la zona}». `como_llegar = enlace_maps(lat, lng)` del sitio donde se deja el coche.

`coste_parking` (los tramos por minuto se suman de forma progresiva; el máximo es tope diario y, desde su minuto de inicio, precio fijo):

```python
def coste_parking(tarifas, minutos):
    por_minuto = [t for t in tarifas if t["periodo"] == "minutos"]
    if not por_minuto:
        return None
    maximo = next((t for t in tarifas if t["periodo"] == "maximo"), None)
    if maximo and minutos >= maximo["desde"]:
        return maximo["precio"]
    total = sum(max(0, min(minutos, t["hasta"]) - max(t["desde"] - 1, 0)) * t["precio"] for t in por_minuto)
    return round(min(total, maximo["precio"]) if maximo else total, 2)
```

`punto_permitido` (solo el borde **exterior** de la zona: los huecos de `zbe_madrid` son autovías donde no se aparca):

```python
def punto_permitido(lng, lat, zona):
    zona_m = a_metros(ZONAS[zona][1])
    exterior = shapely.union_all([shapely.Polygon(p.exterior) for p in shapely.get_parts(zona_m)])
    destino = a_metros(shapely.Point(lng, lat))
    borde = shapely.ops.nearest_points(exterior.boundary, destino)[0]
    dx, dy = borde.x - destino.x, borde.y - destino.y
    d = math.hypot(dx, dy) or 1.0
    fuera = shapely.Point(borde.x + dx / d * DESPLAZAMIENTO_M, borde.y + dy / d * DESPLAZAMIENTO_M)
    if exterior.contains(fuera):
        return None
    p = a_grados(fuera)
    return p.x, p.y
```

- [ ] **Step 1: Tests**

```python
def test_coste_parking():
    assert coste_parking(TARIFAS_RECUERDO, 120) == 4.89
    assert coste_parking(TARIFAS_RECUERDO, 60) == pytest.approx(2.33, abs=0.01)
    assert coste_parking([], 120) is None

def test_coste_parking_tope_diario():
    assert coste_parking(TARIFAS_RECUERDO, 700) == 31.25
    assert coste_parking(TARIFAS_RECUERDO, 1440) == 31.25

def test_minutos_hasta():  # 1 km y 5 km en línea recta hacia el este de Sol
    assert minutos_hasta(*desplazado(SOL, 1000), *SOL) == (17, "a pie")
    assert minutos_hasta(*desplazado(SOL, 5000), *SOL) == (26, "en transporte público")

def test_punto_permitido_centro():
    p = punto_permitido(*SOL, "zbedep_centro")
    assert zonas_en(*p) == ["zbe_madrid"] and distancia_m(*p, *SOL) < 2000

def test_punto_permitido_sin_etiqueta_sale_del_municipio():
    assert zonas_en(*punto_permitido(*SOL, "zbe_madrid")) == []

def test_alternativas_b_en_centro():
    alts = alternativas(DESTINO_SOL, "B", "fuera", "zbedep_centro", 2, HOY, {})
    assert 1 <= len(alts) <= 5 and [a["minutos"] for a in alts] == sorted(a["minutos"] for a in alts)
    assert all(sum(a["tipo"] == t for a in alts) <= 2 for t in ("parking", "estacion"))
    for a in alts:  # nadie manda a un sitio donde no se puede estar
        v = veredicto(a["lng"], a["lat"], "B", "fuera", HOY)
        assert v is None or v[0]["veredicto"] in (("puede", "solo_parking") if a["tipo"] == "parking" else ("puede",))

def test_alternativas_sin_etiqueta_de_fuera():
    alts = alternativas(DESTINO_SOL, "A", "fuera", "zbe_madrid", 2, HOY, {})
    assert alts and {a["tipo"] for a in alts} <= {"estacion", "punto_permitido"}

def test_parking_lleno_se_descarta():
    primero = next(a for a in alternativas(DESTINO_SOL, "B", "fuera", "zbedep_centro", 2, HOY, {}) if a["tipo"] == "parking")
    lleno = {p["id"]: 0 for p in ranking.APARCAMIENTOS if p["nombre"] in primero["nombre"]}
    assert primero["nombre"] not in [a["nombre"] for a in alternativas(DESTINO_SOL, "B", "fuera", "zbedep_centro", 2, HOY, lleno)]

def test_mas_barata_solo_con_coste_completo():
    alts = alternativas(DESTINO_SOL, "B", "fuera", "zbedep_centro", 2, HOY, {})
    baratas = [a for a in alts if a["mas_barata"]]
    assert len(baratas) <= 1 and all(a["coste_eur"] is not None and not a["coste_desde"] for a in baratas)

def test_sin_candidatos_devuelve_lista_vacia(monkeypatch):
    monkeypatch.setattr(ranking, "APARCAMIENTOS", []); monkeypatch.setattr(ranking, "ESTACIONES", [])
    monkeypatch.setattr(ranking, "punto_permitido", lambda *a: None)
    assert alternativas(DESTINO_SOL, "B", "fuera", "zbedep_centro", 2, HOY, {}) == []

def test_paradas_y_enlace():
    assert paradas_cercanas(*SOL)[0]["nombre"] == "Sol" and paradas_cercanas(*SOL)[0]["metros"] < 100
    assert enlace_maps(40.4165, -3.706) == "https://www.google.com/maps/dir/?api=1&destination=40.416500,-3.706000&travelmode=driving"
```
(`SOL = (-3.7035, 40.4168)`, `DESTINO_SOL = {"lng": -3.7035, "lat": 40.4168, "direccion": "Puerta del Sol"}`, `desplazado(p, m)` mueve `m` metros al este con la escala de `geo`, `TARIFAS_RECUERDO` como en Task 4.)

- [ ] **Step 2:** `.venv/bin/pytest tests/test_ranking.py -v` → FAIL.
- [ ] **Step 3:** Implementar `app/ranking.py`.
- [ ] **Step 4:** `.venv/bin/pytest tests/test_ranking.py -v` → PASS.
- [ ] **Step 5:** `git add app tests && git commit -m "feat: alternativas con tiempo, coste y enlace a Google Maps"`

---

### Task 6: API

**Files:**
- Create: `app/main.py`, `tests/test_api.py`
- Origen: `demo/app.py` (middleware de cabeceras, `Consulta`, `Busqueda`, rutas)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces (rutas):
  - `POST /api/comprobar` — `Consulta` del prototipo + `horas: int = Field(2, ge=1, le=24)`. Con `estado = "ok"` añade a la respuesta del prototipo: `"horas"`, `"alternativas"` (solo si el veredicto no es `puede`; `plazas = externos.ocupacion()`, `zona` = la del veredicto), `"paradas_cercanas"` y `"como_llegar"` (enlace al destino, solo si `puede`; si no, `None`).
  - `POST /api/direcciones`, `GET /api/zonas` — como en el prototipo.
  - `GET /api/parkings` → `FeatureCollection` de puntos con `{"nombre", "plazas_libres": int | None, "precio_hora": coste_parking(tarifas, 60)}`.
  - Estáticos de `app/static` montados en `/` al final.
- Arranque: `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`.

- [ ] **Step 1: Tests** (con `TestClient`; `monkeypatch` de `externos.geocodificar` para devolver Calle Mayor 10 — `{"lat": 40.4165, "lng": -3.7060, "muniCode": "28079", "tip_via": "CALLE", "address": "MAYOR", "portalNumber": 10, "postalCode": "28013", "poblacion": "Madrid"}` — y de `externos.ocupacion` → `{}`):

```python
def test_solo_parking_trae_alternativas(cliente):
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "B", "padron": "fuera"}).json()
    assert r["veredicto"] == "solo_parking" and r["alternativas"] and r["como_llegar"] is None and r["horas"] == 2

def test_puede_trae_ruta_y_no_alternativas(cliente):
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "ECO", "padron": "fuera"}).json()
    assert r["veredicto"] == "puede" and r["alternativas"] == [] and r["como_llegar"].startswith("https://www.google.com/maps/dir/")

def test_comprobar_sin_ocupacion(cliente):  # ocupación vacía (SOAP caído): sigue habiendo alternativas
    r = cliente.post("/api/comprobar", json={"direccion": "Calle Mayor 10", "etiqueta": "B", "padron": "fuera", "horas": 4}).json()
    assert r["alternativas"] and all(a["plazas_libres"] is None for a in r["alternativas"])

@pytest.mark.parametrize("cuerpo", [
    {"direccion": "x", "etiqueta": "B", "padron": "fuera", "horas": 0},
    {"direccion": "x", "etiqueta": "B", "padron": "fuera", "horas": 25},
    {"direccion": "x", "etiqueta": "B", "matricula": "0001CVG", "padron": "fuera"},
])
def test_entradas_invalidas(cliente, cuerpo):
    assert cliente.post("/api/comprobar", json=cuerpo).status_code == 422

def test_cabeceras_y_parkings(cliente):
    r = cliente.get("/api/parkings")
    assert r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]
    assert len(r.json()["features"]) >= 50
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_api.py -v` → FAIL.
- [ ] **Step 3:** Implementar `app/main.py` (el frontend ya está en `app/static` desde Task 2).
- [ ] **Step 4:** `.venv/bin/pytest -v` → todo PASS.
- [ ] **Step 5:** `git add app tests && git commit -m "feat: API completa con alternativas y parkings"`

---

### Task 7: Frontend — alternativas, ruta y parkings en el mapa

**Files:**
- Modify: `app/static/index.html`, `app/static/app.js`, `app/static/style.css`

**Interfaces:**
- Consumes: respuesta de `POST /api/comprobar` (Task 6) y `GET /api/parkings`.

- [ ] **Step 1: Resultado.** Con `puede`: junto a «Ver en el mapa», un enlace «Cómo llegar» (`href = r.como_llegar`, `target="_blank"`, `rel="noopener noreferrer"`). Si no, una sección «Alternativas»:
  - «Costes calculados para» y un `<select>` con 1, 2, 3, 4, 6, 8, 12 y 24 h (seleccionado `r.horas`). Al cambiarlo se repite la última petición con `horas` y se vuelve a pintar el resultado; el formulario no se toca.
  - Una lista `<ol>` (ya viene ordenada por tiempo) con, por cada alternativa: nombre; «N min {como} desde que aparcas»; coste como `Intl.NumberFormat("es-ES", {style: "currency", currency: "EUR"})`, con «desde » delante si `coste_desde` y «Precio no disponible» si es `null`; «N plazas libres» si hay dato; distintivo «Más barata» si `mas_barata`; enlace «Cómo llegar».
  - Si la lista viene vacía: «No encontramos alternativas cerca de tu destino.».
  - `paradas_cercanas`, si hay: «Cerca de tu destino: Metro Sol (L1, L2, L3) a 150 m; …».
- [ ] **Step 2: Mapa.** Capa de parkings desde `/api/parkings`: cuadrado azul señal con «P» blanca (como la señal S-17, la letra con CSS `::after`), mismo crecimiento con el zoom que las cámaras (generalizar `iconoCamara` en `iconoPorZoom(clase, conIcono)`), `keyboard: false`, ventana con «Aparcamiento X: N plazas libres» o «sin datos de ocupación». Añadir «Aparcamiento» a la leyenda.
- [ ] **Step 3: Comprobar.** `node --check app/static/app.js`; arrancar el servidor y, en el navegador:
  - Calle Mayor 10, etiqueta B, fuera de Madrid → «Puedes entrar solo para aparcar» y como mucho 5 alternativas ordenadas por minutos.
  - Cambiar a 4 h → cambian los costes de los parkings, no el orden.
  - «Cómo llegar» abre Google Maps con el sitio donde se deja el coche.
  - Calle Mayor 10, sin etiqueta, fuera de Madrid → alternativas solo de estaciones y del punto fuera de Madrid.
  - Calle de Alcalá 300 con ECO → «Puedes entrar» y «Cómo llegar» al destino.
  - El mapa muestra los parkings con «P».
  - Móvil (390 px): sin desbordamiento horizontal.
  - Con la red cortada a `servayto.madrid.es` la comprobación sigue funcionando.
- [ ] **Step 4:** `git add app/static && git commit -m "feat: alternativas, ruta a Google Maps y parkings en el mapa"`

---

### Task 8: Retirar el prototipo y documentar

**Files:**
- Delete: `demo/`
- Modify: `README.md`, `AI_USAGE.md`, `docs/superpowers/specs/2026-11-19-zbe-madrid-design.md`, `docs/arquitectura.excalidraw` (solo textos de cajas, como hasta ahora)

- [ ] **Step 1:** `git rm -r demo` (la base y las descargas ya están en `data/`).
- [ ] **Step 2: README.** Estado, sección «Puesta en marcha» (los comandos de Task 1 Step 0, las cuatro ingestas `python -m ingest.dgt|zonas|aparcamientos|estaciones`, `pytest`, arranque de uvicorn), fuentes nuevas (SOAP de parkings con tarifas; Metro `M4_Red` y Cercanías `M5_Red` del CRTM) y sin enlaces a `demo/`.
- [ ] **Step 3: Documento de diseño.**
  - 8.2: estructura real.
  - 8.4 `ranking.py`: reglas finales, que son 2 + 2 + 1 alternativas; los disuasorios no se etiquetan aparte (un parking lejano aparece con «en transporte público»); coste por tramos y tope diario; billete según corona; paradas EMT fuera de alcance.
  - 7.2: «Cómo llegar» lleva al sitio donde se deja el coche.
  - 10: fuentes (SOAP: 75 parkings, 42 con tarifas y 25 con plazas libres en una sola llamada).
  - 13: quitar lo hecho.
- [ ] **Step 4:** `AI_USAGE.md`: fila de la implementación.
- [ ] **Step 5:** `.venv/bin/pytest -v` → todo PASS; arrancar y repetir un caso de Task 7 Step 3.
- [ ] **Step 6:** `git commit -m "chore: retira el prototipo y actualiza la documentación"`
