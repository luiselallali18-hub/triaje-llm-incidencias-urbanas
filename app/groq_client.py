"""
Cliente de Groq para el triaje de incidencias urbanas.

Este módulo centraliza la conexión con la API de Groq: carga la clave
desde el archivo .env (nunca hardcodeada) y expone una función reutilizable
para clasificar incidencias reportadas por ciudadanos.

Uso:
    from app.groq_client import clasificar_incidencia
    resultado = clasificar_incidencia("Hay un socavón enorme en mi calle")
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "No se encontró GROQ_API_KEY. Copia .env.example a .env "
        "y añade tu clave real de Groq antes de continuar."
    )

client = Groq(api_key=GROQ_API_KEY)

MODEL = "openai/gpt-oss-120b"


CATEGORIAS_VALIDAS = ["bache", "alumbrado", "basura", "agua", "ruido", "otro"]
URGENCIAS_VALIDAS = ["baja", "media", "alta"]

SYSTEM_PROMPT = (
    "Eres un asistente de triaje de incidencias urbanas para un ayuntamiento. "
    "Dado el texto de una incidencia reportada por un ciudadano, clasifica: "
    "1) categoria: una de " + ", ".join(CATEGORIAS_VALIDAS) + " "
    "2) urgencia: una de " + ", ".join(URGENCIAS_VALIDAS) + " "
    "3) resumen: una frase breve en español. "
    "Responde EXCLUSIVAMENTE con un JSON válido, sin texto adicional, "
    "con exactamente estas claves: categoria, urgencia, resumen. "
    'Ejemplo de formato: {"categoria": "bache", "urgencia": "media", "resumen": "..."}'
)


def clasificar_incidencia(texto: str) -> dict:
    """
    Envía el texto de una incidencia a Groq y devuelve un diccionario
    estructurado con las claves: categoria, urgencia, resumen.

    Lanza ValueError si el texto está vacío o si el modelo no devuelve
    un JSON válido con las claves esperadas.
    """
    if not texto or not texto.strip():
        raise ValueError("El texto de la incidencia no puede estar vacío.")

    respuesta = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto},
        ],
        temperature=0.2,
        max_tokens=300,
        response_format={"type": "json_object"},
    )

    contenido = respuesta.choices[0].message.content

    try:
        resultado = json.loads(contenido)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"El modelo no devolvió un JSON válido: {contenido}"
        ) from e

    claves_esperadas = {"categoria", "urgencia", "resumen"}
    if not claves_esperadas.issubset(resultado.keys()):
        raise ValueError(
            f"Faltan claves en la respuesta del modelo. "
            f"Esperadas: {claves_esperadas}, recibidas: {set(resultado.keys())}"
        )

    return resultado


if __name__ == "__main__":
    incidencia_prueba = "Llevo tres días sin luz en la farola de la esquina de mi calle, es una zona muy oscura por la noche."
    print("Enviando incidencia de prueba a Groq...\n")
    resultado = clasificar_incidencia(incidencia_prueba)
    print("Respuesta estructurada del modelo:\n")
    print(f"  Categoría: {resultado['categoria']}")
    print(f"  Urgencia:  {resultado['urgencia']}")
    print(f"  Resumen:   {resultado['resumen']}")