<img width="3950" height="868" alt="2c1c-encadenados-logo-fondo-oscuro" src="https://github.com/user-attachments/assets/6c74e246-e94f-417c-8e98-ac9a276aa3a9" />

# CivicPulseAI · ¿Puedo entrar con mi coche?

Escribe **a dónde vas**, **la etiqueta ambiental de tu coche** (o tu matrícula, si prefieres) y **dónde estás empadronado**, y te decimos con un único mensaje si puedes llegar en coche según las Zonas de Bajas Emisiones (ZBE) de Madrid. Si no puedes, te damos alternativas (parkings permitidos, el punto permitido más cercano, aparcamientos disuasorios con transporte público) ordenadas por tiempo, con la más barata marcada. Un mapa filtrable por etiqueta ambiental muestra por dónde puedes circular, con cámaras, parkings y paradas.

> **Estado (19/11/2026):** diseño cerrado. Hay un [prototipo desechable en `demo/`](demo/README.md) para iterar (veredicto + mapa con datos reales y reglas provisionales).

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
- **Datos:** **SQLite** de solo lectura con las ~38 M matrículas de la DGT, GeoJSON de zonas, cámaras, parkings y paradas, y `reglas.json` escrito a mano desde la Ordenanza 2/2026.
- **Cálculos geográficos:** **Shapely** (¿está la dirección dentro de una zona? ¿cuál es el punto permitido más cercano?).
- **Servicios en directo:** CartoCiudad (IGN) para convertir direcciones en coordenadas y el servicio de parkings en tiempo real del Ayuntamiento, ambos con caché en memoria.
- **Ingesta offline:** scripts que descargan las fuentes oficiales y generan los datos locales.

## 🔗 Fuentes de datos abiertas

| Fuente | Para qué |
|---|---|
| [DGT · Distintivo ambiental](https://sede.dgt.gob.es/es/vehiculos/informacion-de-vehiculos/distintivo-ambiental/) ([fichero diario](https://www.dgt.es/microdatos/salida/distintivoAmbiental/export_dist_ambiental.zip), [ficha en datos.gob.es](https://datos.gob.es/es/catalogo/e00130502-microdatos-de-distintivo-ambiental-de-vehiculos-diarios)) | Etiqueta ambiental de cada matrícula |
| [Madrid · ZBEDEP Distrito Centro: cámaras y calles](https://datos.gob.es/es/catalogo/l01280796-zona-de-bajas-emisiones-de-especial-proteccion-zbedep-distrito-centro-camaras-y-calles) | Perímetro y cámaras de Distrito Centro |
| [Madrid · ZBE: cámaras](https://datos.gob.es/es/catalogo/l01280796-trafico-madrid-zona-de-bajas-emisiones-camaras1) | Cámaras de la ZBE general |
| [Madrid · ZBEDEP Plaza Elíptica](https://datos.gob.es/es/catalogo/l01280796-zona-de-bajas-emisiones-de-especial-proteccion-zbedep-plaza-eliptica1) | Perímetro de Plaza Elíptica |
| [Madrid · Aparcamientos públicos municipales](https://datos.gob.es/es/catalogo/l01280796-aparcamientos-publicos-municipales1) | Parkings y disuasorios |
| [Madrid · Aparcamientos: ocupación en tiempo real](https://datos.gob.es/es/catalogo/l01280796-aparcamientos-publicos-rotacionales-datos-de-ocupacion-en-tiempo-real) | Plazas libres y tarifas |
| [EMT · GTFS](https://datos.gob.es/es/catalogo/l01280796-emt-gtfs-general-transit-feed-specification1) | Paradas de autobús |
| [CRTM · Datos abiertos](https://datos.crtm.es) y [tarifas](https://www.comunidad.madrid/transporte/tarifas) | Estaciones de metro y cercanías; precio del billete |
| [IGN · CartoCiudad](https://www.cartociudad.es) | Dirección → coordenadas |
| [Ordenanza 2/2026 (corrección de errores, BOCM 07/05/2026)](https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/07/BOCM-20260507-49.PDF) · texto publicado en el BOAM nº 10.103 (10/04/2026) | Reglas de acceso a las ZBE |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | Mapa base |

Las fechas reales de cada fichero se comprueban al descargarlo (las del catálogo no siempre son fiables) y se detallan en el documento de diseño.

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
