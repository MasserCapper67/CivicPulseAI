# CivicPulseAI · ¿Puedo entrar con mi coche? — Documento de diseño

- **Fecha:** 19/11/2026
- **Estado:** borrador para aprobación
- **Plan de implementación:** [`docs/superpowers/plans/2026-11-20-app-completa.md`](../plans/2026-11-20-app-completa.md). El prototipo `demo/` sirvió para iterar y se retiró al construir la app definitiva (20/11/2026).
- **Diagrama:** [`docs/arquitectura.excalidraw`](../../arquitectura.excalidraw) (editable en excalidraw.com o en VS Code)
- **Regla del proyecto ([`CLAUDE.md`](../../../CLAUDE.md)):** las funcionalidades deben ser siempre lo más sencillas posible para el usuario final: una única respuesta clara, sin ramas ni opciones que tenga que interpretar.

Las decisiones marcadas **[decisión de diseño]** las tomó quien redactó el documento, no el equipo; se pueden revisar.

---

## 0. Puntos críticos (leer primero)

Ordenados por impacto. Si alguno falla, la app da respuestas falsas o la demo se cae.

**1. Que las reglas sean correctas (`data/reglas.json`)**
- *Riesgo:* un «✔» equivocado le cuesta una multa al usuario (200 € según prensa) y la app pierde su razón de ser.
- *Por qué es difícil:* las reglas solo están en el texto legal (Ordenanza 2/2026, BOAM nº 10.103). La prensa se contradice (B y C en Plaza Elíptica). La moratoria de los empadronados acaba el 31/12/2026. La fecha de entrada en vigor y el ámbito de la ZBE general están sin confirmar. madrid.es bloquea las descargas automáticas.
- *Cómo se cubre:* lectura humana del BOAM al empezar el día 1. Cada regla lleva artículo y fechas de vigencia. Ante la duda, la interpretación más restrictiva, anotada. Un test comprueba que cada combinación tiene exactamente una regla. La app muestra el artículo, la fecha de revisión y un aviso de información orientativa.

**2. Conexión a internet durante la demo**
- *Riesgo:* sin internet no hay geocodificación (CartoCiudad), ni mapa (teselas de OSM), ni parkings en tiempo real. La demo se cae entera.
- *Cómo se cubre:* hotspot del móvil de reserva. Antes de presentar, se consultan las direcciones de la demo para dejarlas en caché (y no se reinicia el servidor después). Los parkings en tiempo real tienen la lista fija de respaldo.

**3. La base de matrículas de la DGT**
- *Riesgo:* sin ella no hay veredicto. Son 101 MB de descarga y 38,7 M filas, y la base no va a git. Medido en el prototipo: 14 s de descarga + 59 s de importación, 0,58 GB.
- *Cómo se cubre:* script de importación que valida (cabecera, más de 30 M filas, solo códigos conocidos) y sustituye la base de golpe. Se ejecuta lo primero el día 1. Copia del `.db` en un USB para el portátil de la demo. Si una matrícula no aparece, el usuario elige la etiqueta a mano.

**4. Geometría de las zonas**
- *Riesgo:* un perímetro mal convertido (coordenadas UTM leídas como lat/lng) o desactualizado da veredictos falsos sin ningún error visible.
- *Datos dudosos:* el perímetro de Distrito Centro es de 2018. En la ZBE general (`ZBE_TM`) se interpreta que `Via_Out=1` son corredores de autovías fuera de la ZBE (sin confirmar en la ordenanza).
- *Cómo se cubre:* conversión con `ogr2ogr -t_srs EPSG:4326`; tests con puntos conocidos (Sol, Plaza Elíptica, Retiro, Getafe); comprobar el perímetro con el anexo de la ordenanza y a ojo en el mapa.

**5. Entender bien la dirección**
- *Riesgo:* «Calle Mayor 10» existe en muchos municipios. Si CartoCiudad devuelve otro, el veredicto es de otro sitio.
- *Cómo se cubre:* autocompletar con sugerencias solo de Madrid, añadir «, Madrid» a la consulta, comprobar `muniCode = 28079` y mostrar siempre la dirección entendida bajo el veredicto («Calle Mayor 10, 28013 Madrid").
- *Trampa comprobada (19/11/2026):* CartoCiudad se equivoca de portal si la consulta lleva el código postal («Calle Alcalá 30, 28014 Madrid» → Alcalá 380; «Calle Mayor 10, 28013» → Mayor 11). Por eso los códigos postales `28xxx` se quitan antes de geocodificar y las sugerencias no los llevan.

**6. Privacidad y seguridad**
- *Riesgo:* matrícula + dirección + padrón revelan dónde vive alguien y a dónde va. Los nombres de parkings y las direcciones vienen de fuera (XSS).
- *Cómo se cubre:* sección 9. No se guarda ni se registra nada; validación con Pydantic; SQLite de solo lectura; `textContent` y ventanas de Leaflet sin HTML; uvicorn en 127.0.0.1; `no-store` en `/api`; cabeceras de seguridad.

**7. Las 6 horas**
- *Riesgo:* el alcance es grande para el tiempo disponible; acabar con muchas piezas a medias.
- *Cómo se cubre:* el orden de prioridad de la sección 12, en el que cada paso deja la app presentable. Camino crítico: reglas + importación de la DGT + geocodificación + veredicto. Motos, rutas y extras quedan fuera.

**8. Estimaciones de tiempo y coste**
- *Riesgo:* los tiempos son aproximados (línea recta × 1,3) y algunos costes no se conocen. Presentados como exactos, engañan.
- *Cómo se cubre:* la app dice «estimado», muestra «—» cuando no hay coste y deja claro que el tiempo cuenta desde que se aparca.

**9. Saber explicarlo**
- *Riesgo:* el jurado puede preguntar por cualquier línea o decisión.
- *Cómo se cubre:* pocas dependencias y sin magia; decisiones y motivos en este documento; `AI_USAGE.md` al día.

## 1. Intención y porqué

Hackatón 2Campus1Code (DAETSISI-DAETSIINF-ORANGE): un MVP web que consuma datos abiertos oficiales y los convierta en un servicio útil para la ciudadanía, con frontend y backend, y que aporte valor más allá de mostrar datos (filtrado, recomendaciones, cruce de fuentes). Se presenta ante un jurado.

El servicio: una persona escribe **a dónde va**, **la etiqueta ambiental de su coche** (o, si quiere, su matrícula) y **dónde está empadronada**, y la app le dice con un único mensaje claro si puede llegar en coche según las Zonas de Bajas Emisiones (ZBE) de Madrid. Si no puede, le ofrece alternativas ordenadas (parkings permitidos, estaciones de metro y cercanías, y el punto permitido más cercano) con tiempo, coste y un enlace de ruta a Google Maps. Un mapa interactivo, filtrable por etiqueta ambiental, muestra por dónde puede y por dónde no puede circular, con cámaras y parkings.

Valor diferencial ante el jurado: cruza cuatro fuentes oficiales (DGT, Ayuntamiento de Madrid, CRTM/EMT, IGN), cita el artículo de la ordenanza en cada respuesta y no guarda datos personales.

## 2. Objetivos

1. **Veredicto único** para dirección + etiqueta (o matrícula) + padrón: «✔ Puedes entrar», «⚠ Solo puedes entrar para aparcar en un parking público» o «✖ No puedes entrar».
2. **Alternativas** cuando no puede entrar (o solo para aparcar): una sola lista ordenada por tiempo, con la más barata marcada, costes calculados para 2 h por defecto y **duración editable** en la pantalla de resultado.
3. **Mapa filtrable por etiqueta**: zonas coloreadas según lo que puede hacer ese coche, cámaras de la ZBE, y parkings (con plazas libres en tiempo real cuando existan). Las paradas cercanas al destino se muestran en el resultado.
4. **Transparencia**: cada veredicto muestra el artículo de la Ordenanza 2/2026 aplicado y la fecha de revisión de las reglas; la app muestra la fecha real de cada fuente de datos.
5. **Seguridad y privacidad** según la sección 9.

## 3. No objetivos

- **Motos** (y por tanto franjas horarias de motos): si la matrícula es de moto, la app responde «Por ahora solo comprobamos coches». Todo lo que no es moto se trata como coche (el fichero de la DGT no distingue turismos de furgonetas).
- Otras ciudades distintas de Madrid. Si la dirección cae fuera del municipio: «Solo cubrimos el municipio de Madrid».
- Cálculo de rutas o navegación. «Cómo llegar» abre Google Maps con la ruta en coche hasta donde se deja el coche (o hasta el destino, si se puede entrar); Google Maps no combina coche y a pie en un mismo enlace.
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

### 7.1 Dos secciones: «1 Incluir datos» y «2 Ver mapa» (decisión del equipo)

El mapa no está siempre a la vista: así el formulario es muy sencillo, sobre todo en móvil.

```
┌──────────────────────────────────────────┐
│  ¿Puedo entrar con mi coche?             │
│  (1) Incluir datos    (2) Ver mapa       │  ← pestañas
├──────────────────────────────────────────┤
│  ¿A dónde vas?   [ Calle Mayor 10    ]   │
│  ¿Cómo identificas tu coche?             │
│  [ Por etiqueta ]  [ Por matrícula ]     │
│  La etiqueta de tu parabrisas            │
│  (0) (ECO) (C) (B) ( ) (H)               │  ← pegatinas
│  ¿Dónde estás empadronado?               │
│  ( ) Fuera de Madrid                     │
│  ( ) En Madrid                           │
│  ( ) En Distrito Centro                  │
│              [ Comprobar ]               │
│  (resultado: señal + [ Ver en el mapa ]) │
└──────────────────────────────────────────┘
```

- **Autocompletar la dirección** (decisión del equipo): a partir de 3 letras aparece una lista de hasta 6 direcciones de Madrid («Calle Alcala 30, Madrid»), con flechas, Intro, Escape y ratón (patrón ARIA combobox). No se usa `<datalist>`: Firefox no refresca bien sus opciones cuando llegan con retraso.
- En escritorio, la cabecera y el formulario van centrados con la misma anchura (30rem); el mapa ocupa todo el ancho.
- Al comprobar, el mapa **no** se abre solo: el resultado (cuando hay veredicto) trae un botón «Ver en el mapa» que abre la sección 2 centrada en el destino.
- Las pestañas son accesibles (`role="tab"`, flechas izquierda/derecha). El mapa se crea la primera vez que se abre su sección: en móvil no se descargan teselas que no se miran.
- **Un solo estado** para formulario, resultado y mapa: si cambia cualquier dato del formulario, el resultado anterior se borra (ya no corresponde); elegir una pegatina en el mapa la elige también en el formulario (y lo pasa a «Por etiqueta»).

- Obligatorios: dirección, padrón y **o la etiqueta o la matrícula, nunca las dos**. Un selector «Por etiqueta / Por matrícula» (por defecto, por etiqueta) muestra solo uno de los dos campos, para que lo que se ve coincida siempre con lo que se comprueba (decisión del equipo). Con matrícula, el resultado indica «según la DGT». El padrón **no** viene marcado por defecto: si se asumiera uno, quien no lo lea recibiría un resultado equivocado.
- La matrícula se acepta con o sin espacios, puntos y guiones, y **se valida antes de buscarla** con las reglas españolas (sección 8.4). Si no es válida, el mensaje dice por qué (p. ej. «Las matrículas actuales no llevan vocales (A)…»).

### 7.2 Resultado

```
✖ Tu coche (etiqueta B) no puede circular por Distrito Centro
  Art. X, Ordenanza 2/2026 · reglas revisadas el DD/MM/2026

  Costes calculados para [ 2 h ▾ ]        Tiempo desde que aparcas
  1. Aparcamiento Plaza de las Descalzas  Más barata   4 min · 5,08 €        [Cómo llegar]
  2. Fuera de ZBEDEP Distrito Centro                  11 min · —             [Cómo llegar]
  3. Metro Bilbao (L1, L4)                            14 min · desde 4,00 €  [Cómo llegar]

  Cerca de tu destino: Metro Sol (L1, L2, L3) a 239 m; …
```
(cifras de ejemplo)

- Con «✔» no se muestran alternativas: solo el mensaje, el artículo y el destino en el mapa.
- **Duración**: selector en el resultado, 2 h por defecto. Al cambiarlo se vuelve a llamar a la API con las nuevas horas; cambian los costes y la marca «más barata», no el orden.
- **Tiempo de cada alternativa** = tiempo desde que el usuario deja el coche hasta su destino (andando o en transporte público). No se pide origen porque sería otro campo. **[decisión de diseño]**
- Si la matrícula tiene un formato válido pero no está en el registro de la DGT: «No encontramos esta matrícula en el registro de la DGT. Revísala o identifica tu coche «Por etiqueta»». No hay un segundo paso para elegir la etiqueta (decisión del equipo).
- Si es moto: «Por ahora solo comprobamos coches».
- **Vehículos históricos** (decisión del equipo, opción A): el desplegable «Por etiqueta» incluye «Vehículo histórico (pegatina H)», así que no hace falta ninguna pregunta más. Por matrícula, las `H 1234 BCD` se reconocen como históricas por su formato (no están en el fichero de distintivos). Un histórico que conserva su matrícula original aparece en la DGT como `SIN DISTINTIVO`: si la matrícula da «sin etiqueta» y el veredicto es «no puede», el resultado añade la nota «Si tu coche lleva la pegatina H de vehículo histórico, compruébalo «Por etiqueta» eligiendo «Histórico»».
- La dirección entendida va en la segunda línea del resultado, justo bajo el veredicto («Tetuan» se entiende como la calle de Tetuán, junto a Sol, no como el distrito).
- Si la dirección no se encuentra o está fuera del municipio, un mensaje que lo dice y deja corregirla.
- El veredicto no depende solo del color: icono + texto (accesibilidad).
- Pie de página: «Información orientativa. La norma vigente es la Ordenanza 2/2026 (enlace)». **[decisión de diseño]**

### 7.3 Mapa

- Leaflet con teselas de OpenStreetMap (con su atribución), centrado en Madrid.
- **Filtro de pegatinas en la sección del mapa**, compartido con el formulario (nunca muestran etiquetas distintas): colorea las zonas para la pegatina y el padrón elegidos; por matrícula, para la etiqueta que devuelve la comprobación. Una línea sobre el mapa dice qué se está viendo («Zonas para un coche con etiqueta B de fuera de Madrid»). Sin padrón elegido, se usa «Fuera de Madrid». **[decisión de diseño]**
- **Zonas coloreadas** según el veredicto, con los colores de las señales: azul (puede), amarillo con borde discontinuo (solo para aparcar), rojo (no puede). Sin etiqueta elegida, en gris. Azul, amarillo y rojo se distinguen mejor que verde y rojo con daltonismo, y el discontinuo no depende del color.

### 7.4 Diseño visual

- **Idea:** el veredicto es una **señal de tráfico** española: disco azul con coche blanco (puedes), aro rojo con coche negro (no puedes) y aro rojo con la **placa complementaria** «Excepto para aparcar en un aparcamiento» (solo para aparcar). Es lo único llamativo de la página; el resto es sobrio.
- **La etiqueta se elige por su aspecto:** una tira de 6 pegatinas redondas con sus colores (0, ECO, C, B, sin etiqueta y H), como se ven en el parabrisas.
- **Color** (semántica de la señalización): hormigón `#E2E4E1` (fondo), blanco `#FFFFFF` (paneles y placas), asfalto `#24272B` (texto), azul señal `#0B4EA2` (permitido y acción principal), rojo señal `#C8102E` (prohibido), amarillo `#F2B705` (condicional y provisional: la franja de «Prototipo»), violeta `#6A2C91` (cámaras). Modo oscuro con los mismos papeles; la señal y la placa no cambian de color.
- **Tipografía:** Barlow (inspirada en la rotulación de carreteras) para el texto y Barlow Condensed para el título, el veredicto y la placa. Servidas desde `static/vendor/fonts/` (licencia OFL); la CSP no admite CDN.
- **Movimiento:** solo la aparición de la señal al comprobar (desactivada con «reducir movimiento»). Al comprobar, la vista se desplaza al resultado.
- **Accesibilidad:** foco visible en todos los controles, radios nativos (ocultos visualmente) bajo las pegatinas y el selector, el resultado en una región `aria-live`, contraste AA también en modo oscuro.
- **Cámaras:** violetas con borde blanco (ningún color de zona es violeta) y tamaño según el zoom: punto de 10 px a escala de ciudad, 18 px con pictograma de cámara desde el zoom 14 y 26 px desde el 16. No entran en el recorrido del tabulador (son 603).
- La ZBE general se dibuja con trazo fino (es todo el municipio, con huecos en las autovías) para no tapar las ZBEDEP.
- **Capas:** zonas, cámaras y los 75 parkings («P» azul, con plazas libres y precio de la primera hora). Las estaciones y las paradas EMT no se pintan en el mapa por ahora.
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

### 8.2 Estructura de carpetas (la construida)

```
app/
  vehiculo.py        matrícula → etiqueta (reglas españolas, SQLite de solo lectura)
  geo.py             zonas, ¿en qué zonas cae un punto?, distancias en metros
  reglas.py          regla vigente y veredicto en un punto
  externos.py        CartoCiudad (direcciones y sugerencias) y plazas libres (SOAP)
  ranking.py         alternativas, coste por tramos, paradas cercanas, enlace a Google Maps
  main.py            rutas, cabeceras de seguridad, estáticos
  static/            index.html · app.js · style.css · img/ · vendor/ (Leaflet, Barlow) · geo/camaras.geojson
ingest/
  __init__.py        registrar_fuente() → data/fuentes.json
  dgt.py  zonas.py  aparcamientos.py  estaciones.py
data/
  reglas.json  zonas.geojson  aparcamientos.json  estaciones.json  fuentes.json   (en git)
  matriculas.db  raw/                                                            (fuera de git)
tests/               pytest: vehiculo, reglas, externos, ingest, ranking, api
requirements.txt     versiones fijadas · pytest.ini
```

### 8.3 API

**`POST /api/comprobar`**

Petición:
```json
{ "direccion": "Calle Mayor 10", "padron": "fuera | madrid | centro", "horas": 2,
  "etiqueta": "CERO | ECO | C | B | A | H", "matricula": "1234 BCD" }
```
Hace falta exactamente uno de los dos, `etiqueta` o `matricula` (si faltan los dos o llegan los dos, 422). Si viene `matricula`, la etiqueta sale del registro de la DGT y `etiqueta_origen` vale `dgt`; si no, `elegida`. `horas` es opcional (2 por defecto).

Respuesta (siempre 200 para los casos esperados; el campo `estado` manda):

| `estado` | Significado | Qué hace el cliente |
|---|---|---|
| `ok` | Hay veredicto | Pinta el resultado |
| `matricula_no_valida` | La matrícula no cumple las reglas españolas; viene `motivo` con el porqué | Muestra el motivo |
| `matricula_no_encontrada` | Formato válido, pero no está en el registro de la DGT | «Revísala, o bórrala y elige tu etiqueta» |
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
  "etiqueta_origen": "elegida | dgt | matricula_historica",
  "nota": "texto o null (aviso del histórico con matrícula original)",
  "horas": 2,
  "alternativas": [
    { "tipo": "parking | estacion | punto_permitido",
      "nombre": "…", "lat": 0, "lng": 0,
      "minutos": 6, "coste_eur": 7.4, "mas_barata": false,
      "plazas_libres": 120, "detalle": "Entrada permitida para aparcar",
      "como_llegar": "https://www.google.com/maps/dir/?api=1&destination=LAT,LNG" }
  ],
  "paradas_cercanas": [ { "nombre": "Sol", "lineas": ["L1","L2","L3"], "metros": 150 } ]
}
```
Errores de validación: 422 (FastAPI). Errores inesperados: 500 con mensaje genérico, sin traza.

**`POST /api/direcciones`** `{ "texto": "alcala 30" }` (3 a 200 caracteres) → `{ "sugerencias": ["Calle Alcala 30, Madrid", …] }`. POST y no GET para que lo escrito no quede en el registro de accesos. Si CartoCiudad falla, lista vacía.

**`GET /api/zonas?etiqueta=B&padron=fuera`** → GeoJSON de las zonas con la propiedad `veredicto` calculada por el mismo motor de reglas (así el mapa nunca duplica la lógica en JavaScript).

**`GET /api/parkings`** → `FeatureCollection` con los 75 parkings: `nombre`, `plazas_libres` (o `null`) y `precio_hora` (primera hora, o `null`). Plazas libres con caché de 5 min; si el servicio falla, todos con `null`.

**Estáticos**: `/` (frontend) y `/geo/camaras.geojson`, con caché del navegador.

### 8.4 Módulos

**vehiculo.py**
- Normaliza (mayúsculas, sin espacios, puntos ni guiones) y **valida con las reglas españolas antes de buscar** (sacadas del propio fichero: sus 38,7 M matrículas tienen 8 formatos):
  - actual (desde 2000), `1234 BCD`, opcionalmente con prefijo `C` (ciclomotor), `R` (remolque), `E` (especial) o `H` (histórico; estas no están en el fichero de la DGT y se tratan directamente como históricas): las 3 letras solo pueden ser `BCDFGHJKLMNPRSTVWXYZ` (sin vocales, Ñ ni Q);
  - provincial (1971-2000), `M 1234 AB`: uno de los 53 códigos de provincia + 4 cifras + 1 o 2 letras (aquí sí hay vocales; nunca Q);
  - numérica (antes de 1971), `M 123456`: provincia + hasta 6 cifras (el fichero las guarda con 6).
  - Ñ, símbolos u otro formato (por ejemplo, una matrícula extranjera) → motivo concreto. Se aplican reglas españolas porque el registro de la DGT solo tiene matrículas españolas; en otros países europeos sí hay vocales. Hay 3 matrículas del fichero con un formato anómalo (`M16103R`) que no pasan: se asume.
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
- Dimensiones: zona × etiqueta (CERO, ECO, C, B, A, H = histórico) × padrón (fuera, madrid, centro) × fecha de hoy. **No hay hora**, salvo que el BOAM tenga franjas horarias para coches (hay que comprobarlo; si las hay, se añade `horas` a la regla y se usa la hora actual).
- Para cada combinación aplicable a hoy debe haber exactamente una regla (lo garantiza un test).
- El contenido sale de leer el BOAM (sección 10). La tabla de la prensa es solo una pista, no la fuente: los coches sin etiqueta empadronados en Madrid podrían circular por la ZBE general hasta el 31/12/2026, pero no por las ZBEDEP; en Distrito Centro, B y C solo para aparcar en un aparcamiento; los vecinos de Distrito Centro tienen acceso; hay fuentes contradictorias sobre B y C en Plaza Elíptica.

**ranking.py** (tal como quedó al implementarlo)
- **Candidatos:** los 75 parkings del servicio SOAP, las estaciones de Metro (242) y Cercanías (111) del CRTM y el punto permitido más cercano. Un parking vale si el veredicto en su posición es `puede`, `solo_parking` o fuera de toda zona, y no está lleno (0 plazas libres); una estación o el punto permitido, si es `puede` o fuera de toda zona. Los disuasorios no se etiquetan aparte: un parking lejano aparece «en transporte público».
- **Se eligen** los 2 mejores parkings, las 2 mejores estaciones y el punto permitido; se ordenan por minutos y se muestran 5 como mucho.
- **Punto permitido:** fuera de la zona **más amplia** que prohíbe en el destino (no la del veredicto, que cita la más específica). Solo cuenta el borde exterior de la zona: los huecos de la ZBE general son autovías. Se aparta 30 m del borde.
- **Tiempo** (*shortcut: sin motor de rutas; línea recta × 1,3*): a pie a 4,5 km/h si sale ≤ 1,5 km; si no, transporte a 25 km/h + 10 min (espera y andar). Cuenta desde que se aparca.
- **Coste:** parkings, con sus tarifas por tramos de minutos (progresivas) y el máximo diario como tope (desde su minuto de inicio, precio fijo). Estación de Metro alcanzada en transporte público: 2,00 € por trayecto en la zona A y 3,00 € fuera (billete combinado), × 2, marcado «desde» porque no incluye aparcar en la calle. Cercanías y la calle: precio no disponible. «Más barata» solo entre costes completos.
- **Tarifas del SOAP poco fiables:** algunos parkings publican como «Minutos» precios que no lo son. En la ingesta, un precio > 0,20 €/min que acaba en 1440 se toma como máximo diario; cualquier otro, o un máximo «desde el minuto 0» junto a precios por minuto, deja el parking con precio «no disponible» (quedan 32 parkings con tarifas).
- **Paradas cercanas:** las 3 estaciones más próximas a ≤ 600 m del destino. Las paradas de autobús EMT quedan fuera por ahora.
- **«Cómo llegar»:** enlace de Google Maps en coche hasta donde se deja el coche.

**externos.py** (llamadas a servicios externos: el código del servidor que pide datos a servicios de terceros)
- **CartoCiudad** `https://www.cartociudad.es/geocoder/api/geocoder/find?q=…` (medido: ~1,3 s; devuelve `lat`, `lng`, `muniCode`, `type`, `postalCode`). Fuera de Madrid si `muniCode != "28079"`. Se quitan los códigos postales `28xxx` (confunden el portal, ver punto crítico 5) y se añade «, Madrid» si no está.
- **CartoCiudad (sugerencias)** `…/geocoder/candidates?q=…&limit=6&municipio_filter=Madrid&no_process=municipio,poblacion,toponimo,expendeduria,ngbe` (medido: ~0,25 s): solo calles y portales de Madrid. Ojo: `municipio_filter=28079` no devuelve nada; hay que pasar el nombre. Caché `lru_cache(maxsize=1024)`. Caché `lru_cache(maxsize=1024)` sobre la dirección normalizada.
- **Parkings en tiempo real**: SOAP `https://servayto.madrid.es/MTPAR_WSINFO/InfoParking?wsdl` (comprobado que responde; incluye ocupación, tarifas y coordenadas). Se construye la petición con `httpx` y se lee con `xml.etree` de la librería estándar. Caché de 5 min; si falla, lista fija.
- Todas las URL externas son fijas en el código y el texto del usuario solo va como parámetro codificado. Tiempo límite: 5 s.

### 8.5 Ingesta (offline, antes de la demo)

- `python -m ingest.dgt`: descarga el ZIP de la DGT (106 MB) a `data/raw/`, abre **solo** el miembro esperado (`export_distintivo_ambiental.txt`) en streaming, comprueba que la cabecera es exactamente `MATRICULA|TIPO DE ETIQUETA` y carga en una base temporal:
  ```sql
  CREATE TABLE v (matricula TEXT PRIMARY KEY, etiqueta INTEGER) WITHOUT ROWID;
  ```
  (medido con el fichero completo del 18/11/2026: 38.729.647 filas, 59 s de importación, 0,58 GB; búsqueda ~7 µs). Códigos que aparecen: `16T0`, `16TE`, `16TC`, `16TB`, `16M0`, `16MC`, `16MB`, `SIN DISTINTIVO`. Valida antes de sustituir: más de 30 M filas y ningún código desconocido. Entonces renombra la base temporal a `matriculas.db` de golpe. Si algo falla, la base anterior queda intacta. Durante la carga, `journal_mode=OFF` y `synchronous=OFF`. Tiempo de importación aún sin medir.
- `python -m ingest.madrid` y `python -m ingest.transporte`: descargan perímetros, cámaras, parkings y paradas y generan `data/geo/*.geojson` en WGS84. Los SHP vienen probablemente en ETRS89 UTM 30N: se convierten una vez con `ogr2ogr -t_srs EPSG:4326` (comando documentado en el README) y el GeoJSON resultante se sube a git. **[decisión de diseño]**: sin dependencias Python de GIS. (Motivo: Leaflet, en el navegador, y Shapely, en el servidor, leen GeoJSON en lat/lng, no SHP.)
- Cada script anota en `data/fuentes.json` la URL, la fecha real del fichero (`Last-Modified`) y la fecha de descarga. Ese fichero alimenta el README y el pie de la app.
- datos.madrid.es puede cortar las conexiones automáticas (el 19/11/2026 lo hizo tras varias descargas). Si un script falla por eso, el fichero se descarga a mano desde el navegador a `data/raw/` y el script lo procesa desde ahí.
- El JSON de parkings municipales tiene un error de sintaxis (`"longitude": --3.65…`): se usa el CSV o el GeoJSON de ese mismo dataset.

## 9. Seguridad y privacidad

### 9.1 Aplicación
1. **Validación en la frontera** con modelos Pydantic: matrícula opcional de hasta 20 caracteres, normalizada y validada con las reglas españolas; exactamente una de etiqueta o matrícula; dirección de 1 a 200 caracteres; `padron` y `etiqueta` como enumerados; `horas` entre 1 y 24.
2. **SQLite en solo lectura** y consultas parametrizadas.
3. **XSS**: todo texto externo o del usuario se inserta con `textContent`. Las ventanas de Leaflet se construyen con nodos del DOM (`bindPopup` interpreta HTML y los nombres de parkings vienen de fuera).
4. **Peticiones a terceros controladas**: hosts fijos, parámetros codificados, tiempo límite de 5 s. El servidor nunca pide una URL que venga del usuario.
5. **Privacidad (RGPD)**: matrícula + dirección + padrón no se guardan ni se registran. El log de acceso de uvicorn no incluye cuerpos de petición; no hay parámetros personales en las URL (la comprobación es POST).
6. **Mismo origen**: sin CORS. Cabeceras: `Content-Security-Policy` (`default-src 'self'`; `img-src 'self' https://tile.openstreetmap.org data:`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (no `no-referrer`: la política de uso de las teselas de OSM exige la cabecera Referer; así solo se envía el origen, nunca la ruta). Leaflet servido desde `static/vendor/`, sin CDN.
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
| DGT · distintivos ambientales | matrícula → etiqueta | ZIP · `https://www.dgt.es/microdatos/salida/distintivoAmbiental/export_dist_ambiental.zip` | 18/11/2026 (diario). El catálogo de datos.gob.es dice 2024: no fiarse del catálogo. |
| datos.madrid.es · ZBEDEP Distrito Centro (dataset 300229) | perímetro y cámaras de Centro | GeoJSON/CSV de cámaras; ZIP con SHP del perímetro | Cámaras: 18/06/2026. **Perímetro: SHP de 2018** («Madrid_Central»): comprobar con el anexo de la ordenanza. |
| datos.madrid.es · ZBE Madrid, cámaras (300654) | cámaras **y perímetro** de la ZBE general | ZIP con SHP: `ZBE_MADRID_CAMARAS` (463 cámaras), `ZBE_TM` (47 polígonos; su unión mide 604 km², el término municipal; `Via_Out=1` parecen corredores de autovías excluidos), `ZBE_MADRID_FOTO_ROJOS` | Ficheros del 29/12/2025 |
| datos.madrid.es · ZBEDEP Plaza Elíptica | perímetro | ZIP con SHP · `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZBEDEP/ZBEDEP_Plaza_Eliptica.zip`: límite, 25 puntos de control, viarios con restricciones y **5 barrios con acceso para residentes** (Zofío, Abrantes, Moscardó, Opañel, Comillas) | Ficheros de 2021 (ZIP de 2025) |
| Ayto. Madrid · parkings (servicio SOAP, dataset 50027) | parkings, tarifas y plazas libres | `POST https://servayto.madrid.es/MTPAR_WSINFO/InfoParking`: `GetListParking` (75 parkings con coordenadas; 25 con plazas libres, en una sola llamada) y `GetDetailParking` (tarifas por tramos) | En directo. Corta las ráfagas de peticiones: la ingesta espera 0,5 s entre llamadas y la app hace como mucho una cada 5 min |
| CRTM · datos.crtm.es | estaciones de metro y cercanías | Servicios ArcGIS `M4_Red` (Metro, 293 registros → 242 estaciones al fundir las repetidas por línea) y `M5_Red` (Cercanías, 111) | Fecha de actualización en el propio dato (`FECHAACTUAL` 29/05/2026) |
| CRTM · tarifas ([comunidad.madrid/transporte/tarifas](https://www.comunidad.madrid/transporte/tarifas)) | precio del billete | [Metro](https://crtm.es/billetes-y-tarifas/billetes-y-abonos/metro/?idPestana=3) · [EMT](https://www.crtm.es/billetes-y-tarifas_old/billetes-y-abonos/autobuses-urbanos-de-madrid-emt/?idPestana=3&lang=) · [Cercanías](https://crtm.es/billetes-y-tarifas_old/billetes-y-abonos/cercanias-ferroviarias/?idPestana=3&lang=) | Consultado el 19/11/2026: Metro zona A 1,50–2,00 €, EMT 1,50 €, 10 viajes 7,30 € (descuento temporal), Cercanías 1,70–5,50 € según zonas |
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
3. Alternativas con parkings, estaciones y punto permitido.
4. Ocupación y tarifas en tiempo real (SOAP).
5. Paradas de transporte y estaciones como candidatos.

Cada paso deja la app presentable por sí solo.

## 13. Lo que queda para quien construya

- **Leer el BOAM nº 10.103** (y la corrección del BOCM) y escribir `reglas.json`: todas las combinaciones, artículo por regla, fechas de vigencia, franjas horarias de coches si las hubiera, y la interpretación más restrictiva ante la duda (anotándola).
- Confirmar el perímetro de Distrito Centro con el anexo y el significado de `Via_Out` en `ZBE_TM`.
- Decidir cómo cubrir a los residentes de los 5 barrios de Plaza Elíptica (hoy la pregunta del padrón no los distingue).
- Revisar las tarifas «de acceso» (3 parkings, hoy ignoradas) y los parkings que se quedan sin precio por datos incoherentes del servicio.
- Confirmar en el BOAM el régimen de los históricos: exentos en la ZBE general (art. 21.3 OMS según la [página de Madrid ZBE](https://madrid.es/go/KilV)), en Plaza Elíptica (lo menciona la corrección del BOCM) y en Distrito Centro (hoy «no puede» por precaución), y si hay límite de días al año (la prensa de 2024-2025 habla de 96). Reglamento de referencia: Real Decreto 892/2024.
