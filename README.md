# Motor de Triaje de Incidencias Urbanas

API asistida por LLM para clasificar reportes ciudadanos de arbolado y zonas verdes (riesgo de caída, plagas, poda, riego, vandalismo), con razonamiento explicable mediante el framework **ReAct** y un dashboard **Human-in-the-loop** para validación por un operador humano.

## Descripción del problema

El departamento de atención ciudadana de Parques y Jardines recibe reportes de texto libre y desestructurado. Este sistema procesa ese texto, razona sobre su urgencia paso a paso, extrae los datos clave en un formato JSON estricto y los presenta en un panel visual para que un operador valide la clasificación antes de su registro final.

## Arquitectura y decisión de diseño

El sistema usa **Ollama** como proveedor local del modelo `llama3.2:3b`, priorizando un ecosistema abierto y ejecutable sin depender de infraestructura de pago ni exponer datos ciudadanos a terceros. Esto garantiza privacidad de los datos y coste cero en la fase de prototipado. El esquema de `Proveedor` (en `app/schemas.py`) ya contempla un proveedor externo adicional (`groq`) para una futura comparación coste/latencia/calidad, aunque de momento solo `ollama` está implementado en `llm_service.py`.

El flujo completo es:

```
Texto del ciudadano
      ↓
Dashboard (Streamlit) ── POST /triage ──▶ API (FastAPI)
                                              ↓
                                    Validación de entrada (Pydantic)
                                              ↓
                                    Prompt ReAct/CoT + few-shot ──▶ Ollama (llama3.2:3b)
                                              ↓
                                    Extracción y validación del JSON (Pydantic)
                                              ↓
                                    Respuesta estructurada + razonamiento
                                              ↓
Dashboard (Streamlit) ◀── 200 / 502 / 503 ───┘
```

## Estructura del proyecto

```
triaje-llm-incidencias-urbanas/
├── app/
│   ├── main.py          # Endpoint FastAPI /triage y manejo de errores
│   ├── llm_service.py   # Llamada a Ollama, extracción y validación del JSON
│   ├── prompts.py       # Prompt de sistema (ReAct/CoT + few-shot + reglas éticas)
│   └── schemas.py        # Esquemas Pydantic de entrada y salida
├── dashboard/
│   └── app.py            # Interfaz Streamlit conectada al endpoint
├── tests/
│   └── test_main.py      # Tests unitarios con mocking de Ollama
├── requirements.txt
└── README.md
```

## Instalación

Requiere Python 3.12 y [Ollama](https://ollama.com/download) instalado localmente.

1. Clona el repositorio y entra en la carpeta del proyecto.

2. Crea y activa un entorno virtual:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Instala las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

4. Descarga el modelo local usado por defecto:

   ```powershell
   ollama pull llama3.2:3b
   ```

## Ejecución

El backend y el dashboard son dos procesos independientes; necesitas dos terminales abiertas simultáneamente (ambas con el `venv` activado).

**Terminal 1 — Backend (FastAPI):**

```powershell
uvicorn app.main:app --reload --reload-dir app
```

La API queda disponible en `http://127.0.0.1:8000`, con documentación interactiva en `http://127.0.0.1:8000/docs`.

> Se limita `--reload-dir` a la carpeta `app/` para evitar que cambios en `dashboard/` o `tests/` reinicien el backend a mitad de una petición en curso.

**Terminal 2 — Dashboard (Streamlit):**

```powershell
streamlit run dashboard/app.py
```

Se abre automáticamente en `http://localhost:8501`.

Antes de clasificar una incidencia, asegúrate de que Ollama esté corriendo (cualquier comando de su CLI, como `ollama list`, lo levanta si estaba apagado).

## Ejemplo de uso

Petición a `POST /triage`:

```json
{
  "texto": "Hay una rama rota colgando sobre un banco en el Retiro",
  "proveedor": "ollama"
}
```

Respuesta:

```json
{
  "categoria": "riesgo_caida",
  "urgencia": "alta",
  "resumen": "Rama rota con riesgo de caída sobre banco transitado",
  "departamento": "Emergencias",
  "razonamiento": "Thought: ... Action: ... Observation: ..."
}
```

## Prompt engineering

El prompt de sistema (`app/prompts.py`) combina:

- **ReAct**: el modelo debe generar explícitamente `Thought` → `Action` → `Observation` antes de la clasificación final tras la palabra clave `Answer:`.
- **Few-shot**: 3 ejemplos completos cubriendo distintas categorías y niveles de urgencia, para fijar el formato de salida.
- **Reglas éticas explícitas**: instrucción directa de ignorar género, origen, raza, nacionalidad, nivel económico o barrio al determinar la urgencia, basándola únicamente en el riesgo físico objetivo y la afluencia de la zona.

## Manejo de errores

La API captura dos escenarios sin detener el servicio:

| Código | Causa |
|---|---|
| 502 | El modelo devolvió una respuesta mal formada (sin `Answer:`, JSON inválido, o claves faltantes) — `RespuestaLLMInvalida`. |
| 503 | No se pudo contactar con el servicio de Ollama (apagado o inaccesible). |
| 422 | El payload de entrada no cumple el esquema `IncidenciaInput` (validación de Pydantic). |

El dashboard traduce cada uno de estos códigos en un mensaje legible para el operador, sin mostrar tracebacks.

## Testing

```powershell
pytest tests/test_main.py -v
```

Los tests usan **mocking** sobre `ollama.chat` (sin necesitar el servicio real corriendo) para cubrir:

1. Respuesta válida del modelo → 200 con los campos estructurados.
2. Alucinación de estructura: falta la palabra clave `Answer:` → 502.
3. JSON con claves faltantes (`departamento` ausente) → 502.
4. Entrada inválida (falta el campo `texto`) → 422.

## Pendiente / próximos pasos

- Integración de un segundo proveedor externo (`groq`, ya contemplado en el enum `Proveedor`) para comparar coste, latencia y calidad frente a Ollama.
- Registro de métricas por petición (tokens de entrada/salida, coste estimado, latencia) en `app/metrics.py`.
- Manejo de rate limits con retry/backoff para el proveedor externo.