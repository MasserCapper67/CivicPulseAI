<img width="3950" height="868" alt="2c1c-encadenados-logo-fondo-oscuro" src="https://github.com/user-attachments/assets/6c74e246-e94f-417c-8e98-ac9a276aa3a9" />

# CivicPulseAI · ¿Puedo entrar con mi coche?

Escribe **a dónde vas**, **la etiqueta ambiental de tu coche** (o tu matrícula, si prefieres) y **dónde estás empadronado**, y te decimos con un único mensaje si puedes llegar en coche según las Zonas de Bajas Emisiones (ZBE) de Madrid. Si no puedes, te damos alternativas (parkings donde sí puedes entrar, estaciones de metro y cercanías, y el punto permitido más cercano) ordenadas por tiempo, con su coste para la duración que elijas, la más barata marcada y un enlace «Cómo llegar» a Google Maps. Un mapa filtrable por etiqueta ambiental muestra por dónde puedes circular, con cámaras y parkings.

> **Estado (20/11/2026):** aplicación completa con datos reales. Las reglas de acceso son provisionales (sacadas de la prensa) hasta comprobarlas en el BOAM.

## ▶️ Puesta en marcha

Necesita Python 3.12+, [uv](https://docs.astral.sh/uv/) y `ogr2ogr` (GDAL).

```bash
uv venv && uv pip install -r requirements.txt
.venv/bin/python -m ingest.dgt            # ≈ 1,5 min: 38,7 M matrículas → data/matriculas.db (0,58 GB, fuera de git)
.venv/bin/python -m ingest.zonas          # perímetros y cámaras oficiales (ya en git)
.venv/bin/python -m ingest.aparcamientos  # ≈ 1 min: parkings y tarifas del Ayuntamiento (ya en git)
.venv/bin/python -m ingest.estaciones     # estaciones de Metro y Cercanías del CRTM (ya en git)
.venv/bin/pytest                          # pruebas
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000>. Solo `ingest.dgt` es imprescindible en un equipo nuevo: el resto de los datos ya está en `data/`. Los servidores del Ayuntamiento cortan las ráfagas de peticiones; si una ingesta falla por eso, basta con reintentarla más tarde.

## 📚 Documentación

| Documento | Contenido |
|---|---|
| [Documento de diseño](docs/superpowers/specs/2026-11-19-zbe-madrid-design.md) | Puntos críticos, objetivos, decisiones, API, módulos, seguridad, fuentes y pruebas |
| [Diagrama de arquitectura](docs/arquitectura.excalidraw) | Editable en [excalidraw.com](https://excalidraw.com) (menú → Abrir) o con la extensión Excalidraw de VS Code |
| [CLAUDE.md](CLAUDE.md) | Reglas del proyecto (sencillez para el usuario final) |
| [AI_USAGE.md](AI_USAGE.md) | Herramientas de IA usadas y su contribución |

## 🏗️ Arquitectura (resumen)

Cliente–servidor en un solo proceso:

- **Frontend:** HTML + CSS + JavaScript sin build, mapa con **Leaflet** y teselas de OpenStreetMap.
- **Backend:** **Python + FastAPI**. Sirve la API JSON y el frontend (mismo origen).
- **Datos:** **SQLite** de solo lectura con las ~38 M matrículas de la DGT; zonas y cámaras en GeoJSON; parkings con tarifas y estaciones en JSON; `reglas.json` escrito a mano desde la Ordenanza 2/2026.
- **Cálculos geográficos:** **Shapely** (¿está la dirección dentro de una zona? ¿cuál es el punto permitido más cercano?).
- **Servicios en directo:** CartoCiudad (IGN) para las direcciones y el autocompletado, y las plazas libres del Ayuntamiento (una llamada cada 5 min como mucho), con caché en memoria.
- **Alternativas:** hasta 2 parkings, 2 estaciones y el punto permitido más cercano, ordenados por el tiempo desde que se aparca; coste real de los parkings por tramos y billete de metro según la zona.
- **Ingesta offline (`ingest/`):** scripts que descargan las fuentes oficiales y generan `data/`.
- **Código:** `app/` (vehiculo, geo, reglas, externos, ranking, main y `static/`), `ingest/`, `tests/` (pytest).

## 🔗 Fuentes de datos abiertas

| Fuente | Para qué |
|---|---|
| [DGT · Distintivo ambiental](https://sede.dgt.gob.es/es/vehiculos/informacion-de-vehiculos/distintivo-ambiental/) ([fichero diario](https://www.dgt.es/microdatos/salida/distintivoAmbiental/export_dist_ambiental.zip), [ficha en datos.gob.es](https://datos.gob.es/es/catalogo/e00130502-microdatos-de-distintivo-ambiental-de-vehiculos-diarios)) | Etiqueta ambiental de cada matrícula |
| [Madrid · ZBEDEP Distrito Centro: cámaras y calles](https://datos.gob.es/es/catalogo/l01280796-zona-de-bajas-emisiones-de-especial-proteccion-zbedep-distrito-centro-camaras-y-calles) | Perímetro y cámaras de Distrito Centro |
| [Madrid · ZBE: cámaras](https://datos.gob.es/es/catalogo/l01280796-trafico-madrid-zona-de-bajas-emisiones-camaras1) | Cámaras de la ZBE general |
| [Madrid · ZBEDEP Plaza Elíptica](https://datos.gob.es/es/catalogo/l01280796-zona-de-bajas-emisiones-de-especial-proteccion-zbedep-plaza-eliptica1) | Perímetro de Plaza Elíptica |
| [Madrid · Aparcamientos: ocupación y servicios](https://datos.gob.es/es/catalogo/l01280796-aparcamientos-publicos-rotacionales-datos-de-ocupacion-en-tiempo-real) (servicio SOAP `servayto.madrid.es/MTPAR_WSINFO/InfoParking`) | 75 parkings con coordenadas, tarifas por tramos y plazas libres en tiempo real |
| [CRTM · Datos abiertos](https://datos.crtm.es): [Metro `M4_Red`](https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M4_Red/FeatureServer/0) y [Cercanías `M5_Red`](https://services5.arcgis.com/UxADft6QPcvFyDU1/arcgis/rest/services/M5_Red/FeatureServer/0) | Estaciones, líneas y corona tarifaria |
| [CRTM · Tarifas](https://www.comunidad.madrid/transporte/tarifas) | Precio del billete de metro |
| [IGN · CartoCiudad](https://www.cartociudad.es) | Dirección → coordenadas y autocompletado |
| [Ordenanza 2/2026 (corrección de errores, BOCM 07/05/2026)](https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/07/BOCM-20260507-49.PDF) · texto publicado en el BOAM nº 10.103 (10/04/2026) | Reglas de acceso a las ZBE |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Mapa base |

Las fechas reales de cada fichero se comprueban al descargarlo (las del catálogo no siempre son fiables) y quedan anotadas en `data/fuentes.json`.

---

## 🚀 Reto: 2Campus1Code - Hackatón DAETSISI-DAETSIINF-ORANGE

Desarrolla un MVP de una aplicación web que consuma al menos una fuente oficial de datos abiertos y la transforme en un servicio útil, visual e interactivo para la ciudadanía. Al acabar, presenta tu solución a los jueces.

### 🎯 Hitos mínimos

- 📊 Consumir datos abiertos de una fuente oficial (API o datasets CSV/JSON/GeoJSON).
- 🏗️ Disponer de frontend y backend (o funciones serverless) con una arquitectura estructurada.
- ✨ Aportar valor más allá de mostrar datos: filtrado, visualizaciones, recomendaciones, cruce de fuentes, etc.
- 🐙 Mantener el código en un repositorio público con un historial de commits coherente.

### 🤖 Uso de IA

Se permite y fomenta el uso de herramientas de IA para el desarrollo.

Durante la evaluación:

- 🧠 Debéis poder explicar cualquier parte del código o decisión técnica
- 📝 El repositorio debe incluir un archivo `AI_USAGE.md` describiendo brevemente las herramientas utilizadas y su contribución al desarrollo.


### ⏱️ Duración

6 horas de desarrollo en total, repartidas entre los dos días que dura la hackatón.

### 📦 Entregables

El repositorio final debe incluir:

- 💻 Código fuente completo y funcional.
- 📄 `AI_USAGE.md`.
- 🔗 Enlaces a las fuentes de datos abiertas utilizadas.
