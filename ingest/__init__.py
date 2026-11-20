"""Scripts de ingesta: descargan las fuentes oficiales y generan data/. Ejecutar como `python -m ingest.<fuente>`."""
import json
from datetime import date

from app.vehiculo import RAIZ

FUENTES = RAIZ / "data" / "fuentes.json"


def registrar_fuente(nombre, url, fecha_fichero):
    """Anota en data/fuentes.json de dónde sale cada dato y la fecha real del fichero (no la del catálogo)."""
    fuentes = json.loads(FUENTES.read_text(encoding="utf-8")) if FUENTES.exists() else {}
    fuentes[nombre] = {"url": url, "fecha_fichero": fecha_fichero, "descargado": date.today().isoformat()}
    FUENTES.write_text(json.dumps(fuentes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
