# Uso de IA

## Herramientas

- **Claude Code** (CLI de Anthropic) con el modelo **Claude Opus 5.5**.

## Fase de diseño (19/11/2026)

| Tarea | Qué hizo la IA | Qué decidió o valida el equipo |
|---|---|---|
| Investigación de fuentes | Búsquedas web en datos.gob.es, datos.madrid.es, DGT, CRTM y boletines oficiales. Comprobó las fechas reales de los ficheros (cabeceras HTTP) en lugar de las del catálogo. Abrió muestras: las primeras ~108.000 filas del fichero de la DGT, el listado de parkings y la descripción del servicio SOAP de ocupación. | Qué fuentes usar y que todo sea de Madrid. |
| Mediciones | Tiempo de respuesta de CartoCiudad (~1,3 s) y tamaño y velocidad de SQLite con la muestra de la DGT (~0,5 GB estimados para 38 M filas, ~7 µs por búsqueda). | Que no hace falta Redis. |
| Arquitectura | Propuso enfoques con sus ventajas e inconvenientes: base de datos frente a scraping, Python frente a Node, rutas completas frente a punto permitido más cercano, caché en memoria frente a Redis, seguridad y privacidad. | Plan A (Python + FastAPI + SQLite + Shapely, frontend HTML/JS + Leaflet), alternativas sin motor de rutas, padrón preguntado antes, duración editable, solo coches, demo en local con Cloudflare para publicar, regla de sencillez en `CLAUDE.md`. |
| Diagrama | Generó `docs/arquitectura.excalidraw` con un script de Python y lo revisó con una vista previa en imagen. | Se edita a mano desde Excalidraw. |
| Prototipo (`demo/`) | Escribió el prototipo desechable: importación de la DGT, conversión de los perímetros oficiales, API FastAPI, página con Leaflet y una autocomprobación. Lo probó de punta a punta con matrículas reales. | Pidió el prototipo; las reglas son provisionales hasta leer el BOAM. |
| Implementación (20/11/2026) | Escribió el plan de implementación (`docs/superpowers/plans/`) y lo ejecutó tarea a tarea con pruebas primero (63 tests de pytest): estructura `app/`, `ingest/`, `data/`, ingesta de parkings con tarifas (servicio SOAP del Ayuntamiento) y de estaciones (CRTM), alternativas con tiempo y coste, enlaces a Google Maps y parkings en el mapa. Lo comprobó en un navegador real con capturas. Al probar con datos reales detectó y corrigió tarifas imposibles del servicio (p. ej. 66 €/min) y un fallo del punto permitido con coches sin etiqueta. | Eligió la ejecución en esta sesión y revisa las decisiones registradas. |
| Documentación | Redactó el documento de diseño (`docs/superpowers/specs/`), los puntos críticos, este archivo y la parte del proyecto del README. | Revisó y aprobó el documento de diseño. |

## Límites y verificación

- La IA **no ha leído todavía el texto oficial** de la Ordenanza 2/2026. Las reglas del prototipo salen de la prensa y son provisionales; las definitivas se escribirán y comprobarán a mano a partir del BOAM.
- La base de matrículas se midió con el fichero completo en el prototipo: 38,7 M filas, 59 s de importación, 0,58 GB.
- El equipo debe poder explicar cualquier línea de código y cualquier decisión. Este archivo se actualizará durante la implementación.
