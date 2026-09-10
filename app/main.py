from fastapi import FastAPI
from app.schemas import IncidenciaInput, TriajeOutput, Categoria, Urgencia

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
    return TriajeOutput(
        categoria=Categoria.riesgo_caida,
        urgencia=Urgencia.alta,
        resumen="Rama rota con riesgo de caída sobre banco transitado",
        departamento="Parques y Jardines",
        razonamiento="[Placeholder] Aquí irá el razonamiento real del LLM.",
    )