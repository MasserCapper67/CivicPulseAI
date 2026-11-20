"""Matrícula → etiqueta ambiental: validación con las reglas españolas y consulta en el fichero de la DGT."""
import re
import sqlite3
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DB = RAIZ / "data" / "matriculas.db"
# El índice en esta lista es lo que se guarda en la base (columna etiqueta).
CODIGOS = ["16T0", "16TE", "16TC", "16TB", "16M0", "16ME", "16MC", "16MB", "SIN DISTINTIVO"]

# Sacadas del propio fichero de la DGT (38,7 M matrículas): letras del formato actual y códigos de provincia antiguos.
CONSONANTES = set("BCDFGHJKLMNPRSTVWXYZ")
PROVINCIAS = set("A AB AL AV B BA BI BU C CA CC CE CO CR CS CU GC GI GR GU H HU IB J L LE LO LU M MA ML MU "
                 "NA O OU P PM PO S SA SE SG SO SS T TE TF TO V VA VI Z ZA".split())
FORMATOS = "Las matrículas españolas son 4 números y 3 consonantes (1234 BCD) o, las antiguas, provincia + números + letras (M 1234 AB)"


def validar_matricula(matricula):
    """Aplica las reglas de las matrículas españolas (las del registro de la DGT).
    Devuelve (matrícula normalizada, None) si el formato es correcto, o (None, motivo) si no lo es."""
    m = re.sub(r"[\s.-]", "", matricula.upper())
    if "Ñ" in m:
        return None, "Las matrículas no llevan la letra Ñ."
    if not re.fullmatch(r"[A-Z0-9]+", m):
        return None, "Una matrícula solo lleva letras y números."
    if actual := re.fullmatch(r"[CREH]?\d{4}([A-Z]{3})", m):  # desde 2000; C ciclomotor, R remolque, E especial, H histórico
        vocales = sorted(set(actual.group(1)) - CONSONANTES - {"Q"})
        if vocales:
            return None, f"Las matrículas actuales no llevan vocales ({', '.join(vocales)}): son 4 números y 3 consonantes, como 1234 BCD."
        if "Q" in actual.group(1):
            return None, "Las matrículas actuales no llevan la letra Q: son 4 números y 3 consonantes, como 1234 BCD."
        return m, None
    if antigua := re.fullmatch(r"([A-Z]{1,2})(\d{4}[A-Z]{1,2}|\d{1,6})", m):  # provincial (1971-2000) o numérica (antes de 1971)
        provincia, resto = antigua.groups()
        if provincia not in PROVINCIAS:
            return None, f"«{provincia}» no es un código de provincia de las matrículas antiguas (M, B, MA, SE…)."
        if "Q" in resto:
            return None, "Las matrículas antiguas no llevan la letra Q."
        return (provincia + resto.zfill(6) if resto.isdigit() else m), None  # el fichero guarda las numéricas con 6 cifras
    return None, f"{FORMATOS}. Si tu coche tiene matrícula extranjera, identifícalo «Por etiqueta»."


def traducir(codigo):
    """Código DGT -> (etiqueta, es_moto). '16MC' -> ('C', True); 'SIN DISTINTIVO' -> ('A', False)."""
    if codigo == "SIN DISTINTIVO":
        return "A", False
    return {"0": "CERO", "E": "ECO", "C": "C", "B": "B"}[codigo[3]], codigo[2] == "M"


def buscar_matricula(matricula):
    with closing(sqlite3.connect(f"file:{DB}?mode=ro", uri=True)) as con:
        fila = con.execute("SELECT etiqueta FROM v WHERE matricula = ?", (matricula,)).fetchone()
    return traducir(CODIGOS[fila[0]]) if fila else None
