from enum import Enum
from pydantic import BaseModel, Field


class Proveedor(str, Enum):
    ollama = "ollama"
    groq = "groq"


class Categoria(str, Enum):
    riesgo_caida = "riesgo_caida"
    plaga_enfermedad = "plaga_enfermedad"
    poda_necesaria = "poda_necesaria"
    riego_sequia = "riego_sequia"
    vandalismo = "vandalismo"


class Urgencia(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class IncidenciaInput(BaseModel):
    texto: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Descripción en texto libre de la incidencia reportada por el ciudadano.",
    )
    proveedor: Proveedor = Field(
        default=Proveedor.ollama,
        description="Proveedor de LLM a utilizar: 'ollama' (local) o 'groq' (externo).",
    )


class TriajeOutput(BaseModel):
    categoria: Categoria
    urgencia: Urgencia
    resumen: str = Field(
        ...,
        description="Resumen de la incidencia en un máximo de 10 palabras.",
    )
    departamento: str = Field(
        ...,
        description="Departamento municipal asignado para atender la incidencia.",
    )
    razonamiento: str = Field(
        ...,
        description="Explicación paso a paso (ReAct/CoT) que justifica la clasificación.",
    )