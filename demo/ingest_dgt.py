"""Descarga el fichero de distintivos de la DGT y genera data/matriculas.db.

Uso: .venv/bin/python ingest_dgt.py
"""
import io
import os
import sqlite3
import time
import urllib.request
import zipfile

URL = "https://www.dgt.es/microdatos/salida/distintivoAmbiental/export_dist_ambiental.zip"
MIEMBRO = "export_distintivo_ambiental.txt"
CABECERA = "MATRICULA|TIPO DE ETIQUETA"
MIN_FILAS = 30_000_000
# El índice en esta lista es lo que se guarda en la base (columna etiqueta).
CODIGOS = ["16T0", "16TE", "16TC", "16TB", "16M0", "16ME", "16MC", "16MB", "SIN DISTINTIVO"]

AQUI = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(AQUI, "data", "raw", "export_dist_ambiental.zip")
DB = os.path.join(AQUI, "data", "matriculas.db")


def descargar():
    if os.path.exists(ZIP):
        print("ZIP ya descargado:", ZIP)
        return
    t = time.time()
    with urllib.request.urlopen(URL, timeout=60) as r, open(ZIP + ".part", "wb") as f:
        print("Last-Modified:", r.headers.get("Last-Modified"))
        while chunk := r.read(1 << 20):
            f.write(chunk)
    os.replace(ZIP + ".part", ZIP)
    print(f"descarga: {time.time() - t:.0f} s")


def filas(texto, desconocidos):
    indice = {c: i for i, c in enumerate(CODIGOS)}
    for linea in texto:
        matricula, _, codigo = linea.rstrip("\r\n").partition("|")
        if codigo in indice:
            yield matricula, indice[codigo]
        else:
            desconocidos[codigo] = desconocidos.get(codigo, 0) + 1


def importar():
    t = time.time()
    tmp = DB + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE TABLE v (matricula TEXT PRIMARY KEY, etiqueta INTEGER NOT NULL) WITHOUT ROWID")
    desconocidos = {}
    # Solo se abre el miembro esperado del ZIP (nunca extractall).
    with zipfile.ZipFile(ZIP) as z, z.open(MIEMBRO) as bruto:
        texto = io.TextIOWrapper(bruto, encoding="latin-1")
        cabecera = next(texto).rstrip("\r\n")
        assert cabecera == CABECERA, f"cabecera inesperada: {cabecera!r}"
        con.executemany("INSERT OR IGNORE INTO v VALUES (?, ?)", filas(texto, desconocidos))
    con.commit()
    n = con.execute("SELECT count(*) FROM v").fetchone()[0]
    con.close()
    print(f"importación: {n:,} filas en {time.time() - t:.0f} s · {os.path.getsize(tmp) / 1e9:.2f} GB")
    assert not desconocidos, f"códigos desconocidos: {desconocidos}"
    assert n > MIN_FILAS, f"demasiado pocas filas: {n}"
    os.replace(tmp, DB)  # sustitución de golpe: si algo falla antes, la base anterior queda intacta
    print("ok:", DB)


if __name__ == "__main__":
    descargar()
    importar()
