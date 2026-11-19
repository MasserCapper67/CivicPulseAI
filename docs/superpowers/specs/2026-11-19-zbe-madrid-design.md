# CivicPulseAI · ¿Puedo entrar con mi coche? — Documento de diseño

- **Fecha:** 19/11/2026
- **Estado:** borrador para aprobación
- **Diagrama:** [`docs/arquitectura.excalidraw`](../../arquitectura.excalidraw) (editable en excalidraw.com o en VS Code)
- **Regla del proyecto ([`CLAUDE.md`](../../../CLAUDE.md)):** las funcionalidades deben ser siempre lo más sencillas posible para el usuario final: una única respuesta clara, sin ramas ni opciones que tenga que interpretar.

Las decisiones marcadas **[decisión de diseño]** las tomó quien redactó el documento, no el equipo; se pueden revisar.

---

## 1. Intención y porqué

Hackatón 2Campus1Code (DAETSISI-DAETSIINF-ORANGE): un MVP web que consuma datos abiertos oficiales y los convierta en un servicio útil para la ciudadanía, con frontend y backend, y que aporte valor más allá de mostrar datos (filtrado, recomendaciones, cruce de fuentes). Se presenta ante un jurado.

El servicio: una persona escribe **a dónde va**, **la matrícula de su coche** y **dónde está empadronada**, y la app le dice con un único mensaje claro si puede llegar en coche según las Zonas de Bajas Emisiones (ZBE) de Madrid. Si no puede, le ofrece alternativas ordenadas (parkings permitidos, el punto permitido más cercano, aparcamientos disuasorios con transporte público) con tiempo y coste. Un mapa interactivo, filtrable por etiqueta ambiental, muestra por dónde puede y por dónde no puede circular, con cámaras, parkings y paradas.

Valor diferencial ante el jurado: cruza cuatro fuentes oficiales (DGT, Ayuntamiento de Madrid, CRTM/EMT, IGN), cita el artículo de la ordenanza en cada respuesta y no guarda datos personales.

## 2. Objetivos

1. **Veredicto único** para dirección + matrícula + padrón: «✔ Puedes entrar», «⚠ Solo puedes entrar para aparcar en un parking público» o «✖ No puedes entrar».
2. **Alternativas** cuando no puede entrar (o solo para aparcar): una sola lista ordenada por tiempo, con la más barata marcada, costes calculados para 2 h por defecto y **duración editable** en la pantalla de resultado.
3. **Mapa filtrable por etiqueta**: zonas coloreadas según lo que puede hacer ese coche, cámaras de la ZBE, parkings (con ocupación en tiempo real cuando exista), disuasorios y paradas de transporte.
4. **Transparencia**: cada veredicto muestra el artículo de la Ordenanza 2/2026 aplicado y la fecha de revisión de las reglas; la app muestra la fecha real de cada fuente de datos.
5. **Seguridad y privacidad** según la sección 9.

## 3. No objetivos

- **Motos** (y por tanto franjas horarias de motos): si la matrícula es de moto, la app responde «Por ahora solo comprobamos coches». Todo lo que no es moto se trata como coche (el fichero de la DGT no distingue turismos de furgonetas).
- Otras ciudades distintas de Madrid. Si la dirección cae fuera del municipio: «Solo cubrimos el municipio de Madrid».
- Cálculo de rutas o navegación. Cada alternativa tiene un enlace «Cómo llegar» que abre Google Maps con el destino.
- Permisos especiales (invitaciones de Distrito Centro, PMR, carga y descarga, servicios esenciales, autorizaciones del Sistema de Gestión de Accesos).
- Excepción por IVTM sin padrón (coches que pagan el impuesto en Madrid pero cuyo titular no está empadronado).
- Cuentas de usuario, historial o guardado de consultas.
- Publicación en internet como objetivo: la demo es en local (ver sección 9.3).
- Leer la normativa de forma automática; scraping de la web de la DGT; Redis.

## 4. Anti-objetivos (fallos aunque «funcione»)

- **Un «✔» equivocado.** Le cuesta al usuario una multa (200 € según prensa). Ante una regla dudosa, se codifica la interpretación más restrictiva y se anota en `reglas.json`.
- Obligar al usuario a interpretar varias ramas («si estás empadronado entonces…»). Siempre una respuesta.
- Guardar o registrar matrícula, dirección o padrón.
- Mostrar reglas o datos sin su fecha.

## 5. Restricciones

- **6 horas de desarrollo** en total, repartidas en dos días.
- El equipo debe poder **explicar cualquier línea** ante el jurado → pocas piezas y pocas dependencias.
- Entregables: código completo en repositorio público con historial de commits coherente, `AI_USAGE.md` actualizado y enlaces a las fuentes de datos en el README.
- La demo corre en un portátil. La base de matrículas (~0,5 GB) se genera en local y no va a git.
- `madrid.es` bloquea las descargas automáticas (403 de Akamai): el texto de la ordenanza hay que descargarlo a mano desde el navegador.

## 6. Enfoques considerados

| Decisión | Elegido | Descartado y por qué |
|---|---|---|
| Etiqueta por matrícula | Fichero diario de la DGT importado a **SQLite** | *Scraping* de sede.dgt.gob.es: no es dato abierto (la hackatón lo pide), la demo dependería de la web de la DGT, hasta 5 s por consulta y se rompe si cambian el HTML. *PostgreSQL*: un servidor más; solo compensaría con PostGIS, innecesario para 3 zonas y unos miles de puntos. |
| Stack | **Plan A**: Python + FastAPI + SQLite + Shapely; frontend HTML/CSS/JS sin build + Leaflet | Plan B (Node/TS + PostgreSQL/PostGIS + React): Docker en cada portátil, más código de unión, más horas. |
| Alternativas | **Opción B**: punto permitido más cercano + zona pintada en el mapa + enlace «Cómo llegar» | Opción A (ruta completa evitando zonas con OpenRouteService): gasta buena parte de las 6 h y depende de una API externa. |
| Reglas | **`reglas.json` escrito a mano** desde el BOAM, con artículo y fechas de vigencia por regla | Interpretar el texto legal automáticamente: no es fiable. |
| Caché | **En memoria del proceso** (`functools.lru_cache` y una caché con caducidad) | Redis: otro servicio que arrancar, asegurar y explicar; solo compensa con varios servidores. |
| Ranking | **Una lista ordenada por tiempo**, la más barata marcada | Selector tiempo/precio: una opción más que interpretar (regla de sencillez). Puntuación mixta tiempo-dinero: obliga a inventar cuánto vale la hora del usuario. |
| Padrón | **Se pregunta antes**, 3 opciones (decisión del equipo) | Nota genérica de «pueden aplicarse excepciones»: rechazada por el equipo, ofrece ramas. |

## 7. Experiencia de usuario

### 7.1 Pantalla única

```
┌──────────────────────────────────────────┐
│  ¿Puedo entrar con mi coche?             │
│  ¿A dónde vas?   [ Calle Mayor 10    ]   │
│  Matrícula       [ 1234 ABC ]            │
│  ¿Dónde estás empadronado?               │
│  ( ) Fuera de Madrid                     │
│  ( ) En Madrid                           │
│  ( ) En Distrito Centro                  │
│              [ Comprobar ]               │
├──────────────────────────────────────────┤
│  (resultado)                             │
├──────────────────────────────────────────┤
│  (mapa · filtro de etiqueta · capas)     │
└──────────────────────────────────────────┘
```

- Los tres campos son obligatorios. El padrón **no** viene marcado por defecto: si se asumiera uno, quien no lo lea recibiría un resultado equivocado.
- La matrícula se acepta con o sin espacios y guiones.

### 7.2 Resultado

```
✖ Tu coche (etiqueta B) no puede circular por Distrito Centro
  Art. X, Ordenanza 2/2026 · reglas revisadas el DD/MM/2026

  Costes calculados para [ 2 h ▾ ]        Tiempo desde que aparcas
  1. Parking Plaza Mayor (entrada permitida)   6 min · 7,40 €  [Cómo llegar]
  2. Punto permitido más cercano + andar      14 min · —       [Cómo llegar]
  3. Disuasorio + Metro L10   💰 más barata    38 min · 3,00 €  [Cómo llegar]

  Cerca de tu destino: Metro Sol (L1, L2, L3) · 150 m
```
(cifras de ejemplo)

- Con «✔» no se muestran alternativas: solo el mensaje, el artículo y el destino en el mapa.
- **Duración**: selector en el resultado, 2 h por defecto. Al cambiarlo se vuelve a llamar a la API con las nuevas horas; cambian los costes y la marca «más barata», no el orden.
- **Tiempo de cada alternativa** = tiempo desde que el usuario deja el coche hasta su destino (andando o en transporte público). No se pide origen porque sería otro campo. **[decisión de diseño]**
- Si la matrícula no está en el fichero de la DGT: «No encontramos tu matrícula. ¿Qué etiqueta tiene tu coche? [0] [ECO] [C] [B] [Sin etiqueta]». Al elegir, se repite la comprobación.
- Si es moto: «Por ahora solo comprobamos coches».
- Si la dirección no se encuentra o está fuera del municipio, un mensaje que lo dice y deja corregirla.
- El veredicto no depende solo del color: icono + texto (accesibilidad).
- Pie de página: «Información orientativa. La norma vigente es la Ordenanza 2/2026 (enlace)». **[decisión de diseño]**

### 7.3 Mapa

- Leaflet con teselas de OpenStreetMap (con su atribución), centrado en Madrid.
- **Filtro de etiqueta**: botones 0 · ECO · C · B · Sin etiqueta. Tras una comprobación se selecciona solo la etiqueta del coche. El padrón se toma del formulario; si aún no se ha respondido, se usa «Fuera de Madrid». **[decisión de diseño]**
- **Zonas coloreadas** según el veredicto para la etiqueta elegida: verde (puede), ámbar (solo para aparcar), rojo (no puede). Sin etiqueta elegida, las zonas se dibujan en gris.
- **Capas** activables: cámaras de la ZBE y de Distrito Centro, parkings (con plazas libres si hay dato en tiempo real), disuasorios, paradas de metro/cercanías y EMT.
- Las ventanas emergentes se construyen con elementos del DOM, nunca con cadenas HTML (sección 9).
- Hay miles de paradas EMT: el mapa usa `preferCanvas: true` y la capa de paradas EMT solo se pinta a partir de cierto nivel de zoom. **[decisión de diseño]**

## 8. Arquitectura

### 8.1 Visión general

Cliente–servidor en un solo proceso: FastAPI sirve la API JSON y los ficheros estáticos del frontend (mismo origen, sin CORS).

```
Navegador (HTML/JS + Leaflet)
   │  POST /api/comprobar · GET /api/zonas · GET /api/parkings · estáticos
   ▼
FastAPI (uvicorn en 127.0.0.1)
   ├─ vehiculo.py   matrícula → etiqueta (SQLite, solo lectura)
   ├─ geo.py        zonas, punto en zona, punto permitido más cercano, cercanos
   ├─ reglas.py     zona × etiqueta × padrón × fecha → veredicto + artículo
   ├─ ranking.py    candidatos permitidos → tiempo, coste, orden
   └─ externos.py   CartoCiudad (geocodificación) · parkings SOAP · cachés
        │
        ▼
data/  matriculas.db (generado, fuera de git) · geo/*.geojson (en git)
       reglas.json (a mano, en git) · fuentes.json (fechas de cada fuente)

ingest/  scripts offline que descargan las fuentes oficiales y generan data/
```

### 8.2 Estructura de carpetas **[decisión de diseño]**

```
app/
  main.py            rutas, estáticos, cabeceras de seguridad, manejo de errores
  vehiculo.py  geo.py  reglas.py  ranking.py  externos.py
  static/            index.html · app.js · style.css · vendor/leaflet/
data/
  reglas.json  fuentes.json  geo/*.geojson
  matriculas.db      (generado; en .gitignore)
  raw/               (descargas; en .gitignore)
ingest/
  dgt.py  madrid.py  transporte.py
tests/
requirements.txt     versiones fijadas
```

### 8.3 API

**`POST /api/comprobar`**

Petición:
```json
{ "direccion": "Calle Mayor 10", "matricula": "1234ABC",
  "padron": "fuera | madrid | centro", "horas": 2,
  "etiqueta": "0 | ECO | C | B | A" }
```
`etiqueta` solo se envía cuando la matrícula no se encontró y el usuario la eligió a mano. `horas` es opcional (2 por defecto).

Respuesta (siempre 200 para los casos esperados; el campo `estado` manda):

| `estado` | Significado | Qué hace el cliente |
|---|---|---|
| `ok` | Hay veredicto | Pinta el resultado |
| `etiqueta_desconocida` | La matrícula no está en el fichero | Muestra el selector de etiqueta |
| `moto` | Es una moto | «Por ahora solo comprobamos coches» |
| `direccion_no_encontrada` | CartoCiudad no la encuentra | Pide corregirla |
| `fuera_de_madrid` | Municipio distinto de 28079 | «Solo cubrimos el municipio de Madrid» |
| `servicio_no_disponible` | CartoCiudad no responde | «Inténtalo de nuevo en unos segundos» |

Con `estado = ok`:
```json
{
  "estado": "ok",
  "veredicto": "puede | solo_parking | no_puede",
  "etiqueta": "B",
  "zona": { "id": "zbedep_centro", "nombre": "ZBEDEP Distrito Centro" },
  "motivo": "Los vehículos con etiqueta B solo pueden entrar para aparcar en un aparcamiento público",
  "fuente": { "norma": "Ordenanza 2/2026", "articulo": "art. X", "url": "…", "revisado": "2026-11-…" },
  "destino": { "direccion": "CALLE MAYOR 10, 28013 Madrid", "lat": 40.4165, "lng": -3.7060 },
  "horas": 2,
  "alternativas": [
    { "tipo": "parking | disuasorio | estacion | punto_permitido",
      "nombre": "…", "lat": 0, "lng": 0,
      "minutos": 6, "coste_eur": 7.4, "mas_barata": false,
      "plazas_libres": 120, "detalle": "Entrada permitida para aparcar",
      "como_llegar": "https://www.google.com/maps/dir/?api=1&destination=LAT,LNG" }
  ],
  "paradas_cercanas": [ { "nombre": "Sol", "lineas": ["L1","L2","L3"], "metros": 150 } ]
}
```
Errores de validación: 422 (FastAPI). Errores inesperados: 500 con mensaje genérico, sin traza.

**`GET /api/zonas?etiqueta=B&padron=fuera`** → GeoJSON de las zonas con la propiedad `veredicto` calculada por el mismo motor de reglas (así el mapa nunca duplica la lógica en JavaScript).

**`GET /api/parkings`** → parkings con plazas libres y tarifas del servicio en tiempo real (caché de 5 min). Si el servicio falla, la lista fija sin ocupación.

**Estáticos**: `/` (frontend) y `/geo/*.geojson` (cámaras, paradas, disuasorios, perímetros), con caché del navegador.

### 8.4 Módulos

**vehiculo.py**
- Normaliza: mayúsculas, sin espacios ni guiones. Valida `^[A-Z0-9]{4,10}$` (frontera de confianza; el fichero de la DGT es la fuente de verdad del formato).
- Consulta `SELECT etiqueta FROM v WHERE matricula = ?` sobre una conexión de solo lectura (`file:…?mode=ro`).
- Códigos del fichero DGT (vistos en una muestra de 108.000 filas): `16T0`, `16TE`, `16TC`, `16TB`, `16M0`, `16MB`, `16MC` y `SIN DISTINTIVO`. Correspondencia: tercer carácter `0`→CERO, `E`→ECO, `C`→C, `B`→B; `SIN DISTINTIVO`→A (sin etiqueta); segundo carácter `M` → moto. La lista completa de códigos se comprueba al importar el fichero entero (sección 10).

**geo.py**
- Carga al arrancar las zonas (GeoJSON) y las convierte a metros con una proyección local equirectangular (x = lon·cos(40,42°)·111 320; y = lat·110 574), con error despreciable dentro de Madrid. Así distancias y «punto más cercano» salen en metros y no en grados. Se usa la geometría «preparada» de Shapely para «¿está dentro?».
- Zonas: `zbe_madrid` (ZBE general), `zbedep_centro`, `zbedep_eliptica`. Un punto puede estar en varias: se evalúan todas y gana la más restrictiva (`no_puede` > `solo_parking` > `puede`).
- **Punto permitido más cercano**: el punto del borde de la zona restrictiva más cercano al destino, desplazado unos 30 m hacia fuera. *shortcut: puede caer en un edificio o parque; si molesta, ajustarlo a la parada o parking permitido más cercano.*
- Cercanos: búsqueda por fuerza bruta sobre unos miles de puntos (suficientemente rápido; sin índice espacial).

**reglas.py** y **`data/reglas.json`**
```json
{
  "norma": { "nombre": "Ordenanza 2/2026, de 24 de marzo, de modificación de la Ordenanza de Movilidad Sostenible",
             "boletin": "BOAM nº 10.103, 10/04/2026", "correccion": "BOCM nº 107, 07/05/2026",
             "url": "…", "revisado": "2026-11-…" },
  "reglas": [
    { "zona": "zbe_madrid", "etiquetas": ["A"], "padron": ["madrid", "centro"],
      "veredicto": "puede", "desde": "AAAA-MM-DD", "hasta": "2026-12-31",
      "articulo": "…", "motivo": "Moratoria para vehículos sin etiqueta de empadronados en Madrid" }
  ]
}
```
- Dimensiones: zona × etiqueta (CERO, ECO, C, B, A) × padrón (fuera, madrid, centro) × fecha de hoy. **No hay hora**, salvo que el BOAM tenga franjas horarias para coches (hay que comprobarlo; si las hay, se añade `horas` a la regla y se usa la hora actual).
- Para cada combinación aplicable a hoy debe haber exactamente una regla (lo garantiza un test).
- El contenido sale de leer el BOAM (sección 10). La tabla de la prensa es solo una pista, no la fuente: los coches sin etiqueta empadronados en Madrid podrían circular por la ZBE general hasta el 31/12/2026, pero no por las ZBEDEP; en Distrito Centro, B y C solo para aparcar en un aparcamiento; los vecinos de Distrito Centro tienen acceso; hay fuentes contradictorias sobre B y C en Plaza Elíptica.

**ranking.py**
- **Candidatos**: parkings públicos, disuasorios, estaciones de metro/cercanías (para aparcar cerca y seguir en transporte) y el punto permitido más cercano. Se descarta todo candidato en cuya ubicación el coche no pueda estar (mismo motor de reglas): con veredicto `no_puede`, o `solo_parking` si el candidato no es un parking. También se descartan los parkings completos.
- **Tiempo** (*shortcut: sin motor de rutas; distancia en línea recta × 1,3. Mejorar con un servicio de rutas si da tiempo*):
  - andando: 4,5 km/h, si la distancia es ≤ 1,5 km;
  - si no, transporte público: 25 km/h + 5 min de espera + 5 min andando hasta la estación y desde ella.
- **Coste**: parkings, tarifa del servicio en tiempo real × horas (si no hay tarifa, `null`). Transporte, billete sencillo × 2 (ida y vuelta), con el precio fijado en el código citando la tarifa del CRTM y su fecha. Aparcar en la calle, `null` (la zona SER no se calcula).
- Orden por minutos; máximo 5 alternativas; `mas_barata` en la de menor coste conocido.

**externos.py**
- **CartoCiudad** `https://www.cartociudad.es/geocoder/api/geocoder/find?q=…` (medido: ~1,3 s; devuelve `lat`, `lng`, `muniCode`, `type`, `postalCode`). Fuera de Madrid si `muniCode != "28079"`. Para evitar coincidencias en otros municipios, se usa el filtro de municipio de la API si existe; si no, se añade «, Madrid» a la consulta. Caché `lru_cache(maxsize=1024)` sobre la dirección normalizada.
- **Parkings en tiempo real**: SOAP `https://servayto.madrid.es/MTPAR_WSINFO/InfoParking?wsdl` (comprobado que responde; incluye ocupación, tarifas y coordenadas). Se construye la petición con `httpx` y se lee con `xml.etree` de la librería estándar. Caché de 5 min; si falla, lista fija.
- Todas las URL externas son fijas en el código y el texto del usuario solo va como parámetro codificado. Tiempo límite: 5 s.

### 8.5 Ingesta (offline, antes de la demo)

- `python -m ingest.dgt`: descarga el ZIP de la DGT (106 MB) a `data/raw/`, abre **solo** el miembro esperado (`export_distintivo_ambiental.txt`) en streaming, comprueba que la cabecera es exactamente `MATRICULA|TIPO DE ETIQUETA` y carga en una base temporal:
  ```sql
  CREATE TABLE v (matricula TEXT PRIMARY KEY, etiqueta INTEGER) WITHOUT ROWID;
  ```
  (medido en una muestra: 14 B/fila → ~0,5 GB para ~38 M filas; búsqueda ~7 µs). Valida antes de sustituir: más de 30 M filas y ningún código desconocido. Entonces renombra la base temporal a `matriculas.db` de golpe. Si algo falla, la base anterior queda intacta. Durante la carga, `journal_mode=OFF` y `synchronous=OFF`. Tiempo de importación aún sin medir.
- `python -m ingest.madrid` y `python -m ingest.transporte`: descargan perímetros, cámaras, parkings y paradas y generan `data/geo/*.geojson` en WGS84. Los SHP vienen probablemente en ETRS89 UTM 30N: se convierten una vez con `ogr2ogr -t_srs EPSG:4326` (comando documentado en el README) y el GeoJSON resultante se sube a git. **[decisión de diseño]**: sin dependencias Python de GIS. (Motivo: Leaflet, en el navegador, y Shapely, en el servidor, leen GeoJSON en lat/lng, no SHP.)
- Cada script anota en `data/fuentes.json` la URL, la fecha real del fichero (`Last-Modified`) y la fecha de descarga. Ese fichero alimenta el README y el pie de la app.
- El JSON de parkings municipales tiene un error de sintaxis (`"longitude": --3.65…`): se usa el CSV o el GeoJSON de ese mismo dataset.

## 9. Seguridad y privacidad

### 9.1 Aplicación
1. **Validación en la frontera** con modelos Pydantic: matrícula normalizada + `^[A-Z0-9]{4,10}$`; dirección de 1 a 200 caracteres; `padron` y `etiqueta` como enumerados; `horas` entre 1 y 24.
2. **SQLite en solo lectura** y consultas parametrizadas.
3. **XSS**: todo texto externo o del usuario se inserta con `textContent`. Las ventanas de Leaflet se construyen con nodos del DOM (`bindPopup` interpreta HTML y los nombres de parkings vienen de fuera).
4. **Peticiones a terceros controladas**: hosts fijos, parámetros codificados, tiempo límite de 5 s. El servidor nunca pide una URL que venga del usuario.
5. **Privacidad (RGPD)**: matrícula + dirección + padrón no se guardan ni se registran. El log de acceso de uvicorn no incluye cuerpos de petición; no hay parámetros personales en las URL (la comprobación es POST).
6. **Mismo origen**: sin CORS. Cabeceras: `Content-Security-Policy` (`default-src 'self'`; `img-src 'self' https://tile.openstreetmap.org data:`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. Leaflet servido desde `static/vendor/`, sin CDN.
7. **Errores genéricos** hacia el cliente; FastAPI sin modo depuración.
8. **Cachés acotadas** (tamaño máximo y caducidad): no se pueden usar para agotar la memoria.
9. **Dependencias**: pocas y con versión fijada (`fastapi`, `uvicorn`, `shapely`, `httpx`); `pip-audit` antes de la demo. No hacen falta claves de API.

### 9.2 Ingesta
- Las descargas se tratan como no fiables: del ZIP solo se lee el miembro esperado (nunca `extractall`) y se validan formato y número de filas antes de sustituir la base.
- Solo HTTPS.

### 9.3 Publicación
- La demo es en local. uvicorn escucha solo en `127.0.0.1`.
- Si se publica, se hace con **Cloudflare Tunnel**, que pone el HTTPS y, con un dominio en una cuenta de Cloudflare, el límite de peticiones (el túnel rápido `trycloudflare.com` no permite reglas). Detrás del túnel todas las peticiones llegan desde 127.0.0.1, así que el límite no se implementa en la app.
- Las respuestas de `/api/*` llevan `Cache-Control: no-store` para que Cloudflare no las guarde. Los estáticos sí se pueden cachear.

## 10. Fuentes de datos (fechas comprobadas el 19/11/2026)

| Fuente | Uso | Formato / URL | Fecha real |
|---|---|---|---|
| DGT · distintivos ambientales | matrícula → etiqueta | ZIP · `https://www.dgt.es/microdatos/salida/distintivoAmbiental/export_dist_ambiental.zip` | 13/11/2026 (diario). El catálogo de datos.gob.es dice 2024: no fiarse del catálogo. |
| datos.madrid.es · ZBEDEP Distrito Centro (dataset 300229) | perímetro y cámaras de Centro | GeoJSON/CSV de cámaras; ZIP con SHP del perímetro | Cámaras: 18/06/2026. **Perímetro: SHP de 2018** («Madrid_Central»): comprobar con el anexo de la ordenanza. |
| datos.madrid.es · ZBE Madrid, cámaras | cámaras de la ZBE general | CSV/XLSX/SHP · datos.gob.es `l01280796-trafico-madrid-zona-de-bajas-emisiones-camaras1` | 04/06/2026 |
| datos.madrid.es · ZBEDEP Plaza Elíptica | perímetro | SHP · datos.gob.es `l01280796-zona-de-bajas-emisiones-de-especial-proteccion-zbedep-plaza-eliptica1` | URL de descarga por confirmar |
| Límite de la ZBE general | perímetro | Por localizar (límite municipal o polígono propio de la ZBE) | Comprobar en la ordenanza si la ZBE general es todo el término municipal |
| datos.madrid.es · aparcamientos públicos municipales (202625) | parkings y disuasorios | CSV/GeoJSON (el JSON está mal formado) | 13/11/2026 · 63 aparcamientos (39 mixtos, 19 públicos, 5 disuasorios) con coordenadas; sin tarifas |
| Ayto. Madrid · parkings en tiempo real (50027) | ocupación y tarifas | SOAP · `https://servayto.madrid.es/MTPAR_WSINFO/InfoParking?wsdl` | En directo; responde (19/11/2026) |
| EMT · GTFS (datos.madrid.es) | paradas de autobús | GTFS (`stops.txt`) | Comprobar al descargar |
| CRTM · datos.crtm.es | estaciones de metro y cercanías; precio del billete | Descargas del portal; licencia: citar al CRTM | Comprobar al descargar |
| IGN · CartoCiudad | geocodificación | API REST, sin clave | En directo |
| Ordenanza 2/2026, de 24 de marzo | reglas | BOAM nº 10.103 (10/04/2026); corrección en BOCM nº 107 (07/05/2026): `https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/07/BOCM-20260507-49.PDF` | Entrada en vigor por confirmar en el texto (la prensa dice 07/04/2026; el BOAM es del 10/04/2026) |
| OpenStreetMap | teselas del mapa | `tile.openstreetmap.org` con atribución | — |

## 11. Pruebas (mínimas)

- **Reglas completas**: para cada zona × etiqueta × padrón en la fecha de hoy, exactamente una regla aplicable. Más los casos clave (B en Centro y fuera de Madrid → `solo_parking`; A en Madrid sin empadronar → `no_puede`; A empadronado antes y después del 31/12/2026).
- **Vehículo**: normalización de matrícula y tabla de códigos DGT (incluida moto y `SIN DISTINTIVO`).
- **Geo**: Puerta del Sol → `zbedep_centro`; un punto de Plaza Elíptica → `zbedep_eliptica`; un punto de Retiro → solo `zbe_madrid`; un punto de Getafe → fuera.
- **API**: una prueba de humo con `TestClient` y los servicios externos simulados.
- **Escenarios de demo** fijados de antemano: una matrícula real de cada etiqueta sacada del fichero (dato público) y 2 o 3 direcciones (Calle Mayor 10, una de Plaza Elíptica y una fuera de las ZBEDEP). Antes de presentar se consultan una vez para dejar CartoCiudad en caché.

## 12. Prioridad si falta tiempo

1. Veredicto (formulario → matrícula → zona → reglas → mensaje con artículo).
2. Mapa con zonas coloreadas por etiqueta y cámaras.
3. Alternativas con parkings y disuasorios de la lista fija.
4. Ocupación y tarifas en tiempo real (SOAP).
5. Paradas de transporte y estaciones como candidatos.

Cada paso deja la app presentable por sí solo.

## 13. Lo que queda para quien construya

- **Leer el BOAM nº 10.103** (y la corrección del BOCM) y escribir `reglas.json`: todas las combinaciones, artículo por regla, fechas de vigencia, franjas horarias de coches si las hubiera, y la interpretación más restrictiva ante la duda (anotándola).
- Confirmar el perímetro de Distrito Centro con el anexo, localizar el SHP de Plaza Elíptica y el polígono de la ZBE general.
- Explorar las operaciones del SOAP de parkings y el formato de las tarifas.
- Fijar el precio del billete con la tarifa vigente del CRTM y citarla.
- Comprobar el filtro de municipio de CartoCiudad.
- Medir el tiempo de importación del fichero completo de la DGT.
- Actualizar `AI_USAGE.md` y añadir al README los enlaces a las fuentes.
