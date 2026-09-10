import json
import re
import time
import ollama
from app.prompts import SYSTEM_PROMPT
from app.schemas import TriajeOutput


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
    resultado = TriajeOutput(
        categoria=datos_json["categoria"],
        urgencia=datos_json["urgencia"],
        resumen=datos_json["resumen"],
        departamento=datos_json["departamento"],
        razonamiento=texto_respuesta.split("Answer:")[0].strip(),
    )

    metadatos = {
        "proveedor": "ollama",
        "modelo": modelo,
        "latencia_segundos": round(latencia_segundos, 3),
        "tokens_entrada": respuesta.get("prompt_eval_count", 0),
        "tokens_salida": respuesta.get("eval_count", 0),
    }

    return resultado, metadatos