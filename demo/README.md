# Prototipo desechable · ¿Puedo entrar con mi coche?

> **Esto es un prototipo para iterar, no la app final.** La versión definitiva se construirá siguiendo el [documento de diseño](../docs/superpowers/specs/2026-11-19-zbe-madrid-design.md).

## Qué hace (iteración 1)

- Formulario: dirección + coche identificado **por etiqueta o por matrícula** (un selector; solo se ve un campo) + padrón → veredicto único (✔ / ⚠ solo para aparcar / ✖), con el motivo, la dirección entendida y la norma.
- La matrícula se valida con las reglas españolas antes de buscarla y, si no es válida, se explica por qué (vocales, Q, Ñ, provincia inexistente, formato extranjero…). Formato válido pero no registrado → mensaje para revisarla o usar «Por etiqueta». Moto → «Por ahora solo comprobamos coches». Históricos: opción «Vehículo histórico (pegatina H)» o matrícula `H 1234 BCD`.
- Mapa con las 3 zonas oficiales coloreadas según la etiqueta elegida y las 603 cámaras.

**Aún no:** alternativas (parkings, disuasorios, punto permitido más cercano), duración, paradas de transporte.

## Qué es real y qué no

| Pieza | Estado |
|---|---|
| Matrícula → etiqueta | **Real**: fichero de la DGT del 18/11/2026, 38.729.647 matrículas |
| Perímetros de las zonas y cámaras | **Reales**: datos.madrid.es y geoportal.madrid.es |
| Dirección → coordenadas | **Real**: CartoCiudad (IGN) |
| Reglas (`data/reglas.json`) | **PROVISIONALES**: sacadas de la prensa, sin verificar en el BOAM. Ante la duda, lo más restrictivo |

## Arrancar

Necesita Python 3.12+, [uv](https://docs.astral.sh/uv/) y `ogr2ogr` (GDAL).

```bash
cd demo
uv venv && uv pip install fastapi uvicorn shapely httpx
.venv/bin/python ingest_dgt.py      # ~1,5 min: descarga 101 MB y crea data/matriculas.db (0,58 GB)
.venv/bin/python ingest_zonas.py    # perímetros y cámaras oficiales
.venv/bin/python test_demo.py       # autocomprobación
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

Abrir <http://127.0.0.1:8000>.

## Matrículas de prueba (del fichero público de la DGT)

| Etiqueta | Matrícula |
|---|---|
| 0 emisiones | 0009NCW |
| ECO | 0003MXP |
| C | 0000MFC |
| B | 0001CVG |
| Sin etiqueta | 0002CZP |
| Moto (C) | 0003HLN |
| Histórica (por formato) | H 1234 BCD |
| Formato válido que no existe | 9999 ZZZ |
| No válida (vocal) | 1234 ABC |
| Antigua provincial | AB 6893 ET |

Direcciones útiles: `Calle Mayor 10` (Distrito Centro), `Vía Lusitana 1` (Plaza Elíptica), `Calle de Alcalá 300` (solo ZBE general), `Calle Madrid 1, Getafe` (fuera de Madrid).
