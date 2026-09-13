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

SYSTEM_PROMPT = (
    "Eres un asistente de triaje de incidencias urbanas para un ayuntamiento. "
    "Dado el texto de una incidencia reportada por un ciudadano, clasifica: "
    "1) categoria (ej: bache, alumbrado, basura, agua, ruido, otro), "
    "2) urgencia (baja, media, alta), "
    "3) un resumen breve en una frase. "
    "Responde siempre en español, de forma concisa y estructurada."
)


def clasificar_incidencia(texto: str) -> str:
    """
    Envía el texto de una incidencia a Groq y devuelve la clasificación
    generada por el modelo (categoría, urgencia y resumen).
    """
    respuesta = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto},
        ],
        temperature=0.2,
        max_tokens=300,
    )
    return respuesta.choices[0].message.content


if __name__ == "__main__":
    incidencia_prueba = "Llevo tres días sin luz en la farola de la esquina de mi calle, es una zona muy oscura por la noche."
    print("Enviando incidencia de prueba a Groq...\n")
    resultado = clasificar_incidencia(incidencia_prueba)
    print("Respuesta del modelo:\n")
    print(resultado)