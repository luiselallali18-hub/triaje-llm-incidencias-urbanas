import os
from groq import Groq
from groq import RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json
import re
import time
import ollama
from app.prompts import SYSTEM_PROMPT
from app.schemas import TriajeOutput

from dotenv import load_dotenv
load_dotenv()

_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class RespuestaLLMInvalida(Exception):
    """Se lanza cuando el LLM no devuelve un JSON parseable o válido."""
    pass


def _extraer_json(texto_respuesta: str) -> dict:
    if "Answer:" not in texto_respuesta:
        raise RespuestaLLMInvalida("El modelo no incluyó la palabra clave 'Answer:' en su respuesta.")

    bloque_tras_answer = texto_respuesta.split("Answer:", 1)[1]

    coincidencia = re.search(r"\{.*\}", bloque_tras_answer, re.DOTALL)
    if not coincidencia:
        raise RespuestaLLMInvalida("No se encontró un objeto JSON después de 'Answer:'.")

    try:
        return json.loads(coincidencia.group(0))
    except json.JSONDecodeError as error:
        raise RespuestaLLMInvalida(f"El JSON encontrado no es válido: {error}")


def clasificar_con_ollama(texto_incidencia: str, modelo: str = "llama3.2:3b") -> tuple[TriajeOutput, dict]:
    inicio = time.perf_counter()

    respuesta = ollama.chat(
        model=modelo,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f'Texto del ciudadano: "{texto_incidencia}"'},
        ],
        options={"temperature": 0.2},
    )

    latencia_segundos = time.perf_counter() - inicio
    texto_respuesta = respuesta["message"]["content"]

    datos_json = _extraer_json(texto_respuesta)
    
    try:
        resultado = TriajeOutput(
            categoria=datos_json["categoria"],
            urgencia=datos_json["urgencia"],
            resumen=datos_json["resumen"],
            departamento=datos_json["departamento"],
            razonamiento=texto_respuesta.split("Answer:")[0].strip(),
    )
    except KeyError as clave_faltante:
        raise RespuestaLLMInvalida(
            f"El JSON del modelo no incluye la clave requerida: {clave_faltante}"
        )

    metadatos = {
        "proveedor": "ollama",
        "modelo": modelo,
        "latencia_segundos": round(latencia_segundos, 3),
        "tokens_entrada": respuesta.get("prompt_eval_count", 0),
        "tokens_salida": respuesta.get("eval_count", 0),
    }

    return resultado, metadatos


@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _llamar_groq(modelo: str, texto_incidencia: str):
    return _groq_client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f'Texto del ciudadano: "{texto_incidencia}"'},
        ],
        temperature=0.2,
    )


def clasificar_con_groq(texto_incidencia: str, modelo: str = "openai/gpt-oss-120b") -> tuple[TriajeOutput, dict]:
    inicio = time.perf_counter()

    try:
        respuesta = _llamar_groq(modelo, texto_incidencia)
    except RateLimitError as error:
        raise ConnectionError(f"Rate limit de Groq excedido tras reintentos: {error}")

    latencia_segundos = time.perf_counter() - inicio
    texto_respuesta = respuesta.choices[0].message.content

    datos_json = _extraer_json(texto_respuesta)

    try:
        resultado = TriajeOutput(
            categoria=datos_json["categoria"],
            urgencia=datos_json["urgencia"],
            resumen=datos_json["resumen"],
            departamento=datos_json["departamento"],
            razonamiento=texto_respuesta.split("Answer:")[0].strip(),
        )
    except KeyError as clave_faltante:
        raise RespuestaLLMInvalida(
            f"El JSON del modelo no incluye la clave requerida: {clave_faltante}"
        )

    metadatos = {
        "proveedor": "groq",
        "modelo": modelo,
        "latencia_segundos": round(latencia_segundos, 3),
        "tokens_entrada": respuesta.usage.prompt_tokens,
        "tokens_salida": respuesta.usage.completion_tokens,
    }

    return resultado, metadatos
