import time
import ollama
from fastapi import FastAPI, HTTPException
from app.schemas import IncidenciaInput, TriajeOutput
from app.llm_service import clasificar_con_ollama, clasificar_con_groq, RespuestaLLMInvalida
from app.metrics import registrar_peticion

app = FastAPI(
    title="Motor de Triaje de Incidencias Urbanas",
    description="API para clasificar incidencias de arbolado y zonas verdes mediante LLM.",
    version="0.1.0",
)


@app.get("/")
def raiz():
    return {"mensaje": "Motor de triaje activo. Consulta /docs para ver el endpoint."}


@app.post("/triage", response_model=TriajeOutput)
def triage(incidencia: IncidenciaInput):
    inicio = time.perf_counter()

    try:
        if incidencia.proveedor.value == "groq":
            resultado, metadatos = clasificar_con_groq(incidencia.texto)
        else:
            resultado, metadatos = clasificar_con_ollama(incidencia.texto)

        registrar_peticion(
            proveedor=metadatos["proveedor"],
            modelo=metadatos["modelo"],
            tokens_entrada=metadatos["tokens_entrada"],
            tokens_salida=metadatos["tokens_salida"],
            latencia_segundos=metadatos["latencia_segundos"],
            exito=True,
        )

        return resultado

    except RespuestaLLMInvalida as error:
        registrar_peticion(
            proveedor=incidencia.proveedor.value,
            modelo="desconocido",
            tokens_entrada=0,
            tokens_salida=0,
            latencia_segundos=time.perf_counter() - inicio,
            exito=False,
        )
        raise HTTPException(
            status_code=502,
            detail=f"El modelo devolvió una respuesta con formato incorrecto: {error}",
        )

    except (ollama.ResponseError, ConnectionError) as error:
        registrar_peticion(
            proveedor=incidencia.proveedor.value,
            modelo="desconocido",
            tokens_entrada=0,
            tokens_salida=0,
            latencia_segundos=time.perf_counter() - inicio,
            exito=False,
        )
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo contactar con el servicio de Ollama: {error}",
        )
