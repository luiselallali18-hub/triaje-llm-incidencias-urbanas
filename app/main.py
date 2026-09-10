import ollama
from fastapi import FastAPI, HTTPException
from app.schemas import IncidenciaInput, TriajeOutput
from app.llm_service import clasificar_con_ollama, RespuestaLLMInvalida

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
    try:
        resultado, metadatos = clasificar_con_ollama(incidencia.texto)
        return resultado

    except RespuestaLLMInvalida as error:
        raise HTTPException(
            status_code=502,
            detail=f"El modelo devolvió una respuesta con formato incorrecto: {error}",
        )

    except (ollama.ResponseError, ConnectionError) as error:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo contactar con el servicio de Ollama: {error}",
        )