"""
Registro de métricas por petición: tokens, coste estimado y latencia.

Cada llamada al LLM (Ollama o, en el futuro, Groq) debe registrarse aquí
para poder analizar coste y rendimiento por proveedor desde el dashboard.
"""

import csv
import os
from datetime import datetime, timezone

RUTA_CSV = os.path.join(os.path.dirname(__file__), "..", "metrics.csv")

COLUMNAS = [
    "timestamp",
    "proveedor",
    "modelo",
    "tokens_entrada",
    "tokens_salida",
    "coste_estimado_usd",
    "latencia_segundos",
    "exito",
]

PRECIOS_POR_MILLON_TOKENS = {
    "ollama": {"entrada": 0.0, "salida": 0.0},
    "groq": {"entrada": 0.05, "salida": 0.08},
}


def _calcular_coste(proveedor: str, tokens_entrada: int, tokens_salida: int) -> float:
    precios = PRECIOS_POR_MILLON_TOKENS.get(proveedor, {"entrada": 0.0, "salida": 0.0})
    coste_entrada = (tokens_entrada / 1_000_000) * precios["entrada"]
    coste_salida = (tokens_salida / 1_000_000) * precios["salida"]
    return round(coste_entrada + coste_salida, 8)


def _asegurar_csv_existe() -> None:
    if not os.path.exists(RUTA_CSV):
        with open(RUTA_CSV, mode="w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)
            escritor.writerow(COLUMNAS)


def registrar_peticion(
    proveedor: str,
    modelo: str,
    tokens_entrada: int,
    tokens_salida: int,
    latencia_segundos: float,
    exito: bool,
) -> None:
    """Añade una fila al historial de métricas en metrics.csv."""
    _asegurar_csv_existe()

    coste_estimado = _calcular_coste(proveedor, tokens_entrada, tokens_salida)

    with open(RUTA_CSV, mode="a", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow([
            datetime.now(timezone.utc).isoformat(),
            proveedor,
            modelo,
            tokens_entrada,
            tokens_salida,
            coste_estimado,
            round(latencia_segundos, 3),
            exito,
        ])