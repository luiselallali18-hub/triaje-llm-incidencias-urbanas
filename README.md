# Motor de Triaje de Incidencias Urbanas

API asistida por LLM para clasificar reportes ciudadanos de arbolado y zonas verdes (riesgo de caída, plagas, poda, riego, vandalismo), con razonamiento explicable mediante el framework **ReAct** y un dashboard **Human-in-the-loop** para validación por un operador humano.

## Descripción del problema

El departamento de atención ciudadana de Parques y Jardines recibe reportes de texto libre y desestructurado. Este sistema procesa ese texto, razona sobre su urgencia paso a paso, extrae los datos clave en un formato JSON estricto y los presenta en un panel visual para que un operador valide la clasificación antes de su registro final.

## Arquitectura y decisión de diseño

El sistema compara dos proveedores de LLM, tal como exige el proyecto:

- **Ollama** (local, modelo `llama3.2:3b`): ecosistema abierto, ejecutable sin depender de infraestructura de pago ni exponer datos ciudadanos a terceros. Coste cero y máxima privacidad, ideal para la fase de prototipado.
- **Groq** (externo, modelo `openai/gpt-oss-120b`): API comercial de baja latencia, usada como referencia de comparación en coste, velocidad y calidad frente al modelo local.

Ambos proveedores comparten el mismo prompt de sistema (`app/prompts.py`), con razonamiento ReAct/CoT, few-shot y reglas éticas explícitas, para que la comparación entre ellos sea justa.

### Backend y dashboard: una sola lógica, dos puntos de entrada

El backend expone un endpoint REST con FastAPI (`app/main.py`) que valida entrada y salida con Pydantic y captura errores del LLM sin caerse. El dashboard de Streamlit (`dashboard/app.py`) **no llama a ese endpoint por HTTP**: importa directamente las funciones de `app/llm_service.py` y `app/metrics.py`.

Esta decisión es intencional, no un atajo: Streamlit Community Cloud solo puede ejecutar un proceso Streamlit, no un segundo servidor FastAPI en `127.0.0.1` en paralelo. Al reutilizar la misma lógica de clasificación y el mismo manejo de excepciones (`RespuestaLLMInvalida`, `ollama.ResponseError`, `ConnectionError`) que usa el endpoint, el dashboard funciona igual de bien desplegado en la nube que en local, sin duplicar código ni comprometer la validación type-safe. El endpoint FastAPI se mantiene como servicio independiente, documentado y testeado, para cualquier integración externa (por ejemplo, un sistema municipal que quiera consumir la API directamente).

El flujo completo:

```
Texto del ciudadano
      |
      v
Dashboard (Streamlit) ----+-- llama directamente a --> app/llm_service.py
                          |                                  |
API (FastAPI) /triage ----+                                  v
                                            Validacion de entrada (Pydantic)
                                                              |
                                                              v
                                      Prompt ReAct/CoT + few-shot --> Ollama o Groq
                                                              |
                                                              v
                                      Extraccion y validacion del JSON (Pydantic)
                                                              |
                                                              v
                                      Respuesta estructurada + razonamiento
                                                              |
                                                              v
                                      Registro de metricas (metrics.csv)
                                                              |
                                                              v
                              Dashboard muestra resultado / mensaje de error controlado
```

### Inicialización perezosa del cliente Groq

El cliente de Groq se crea solo la primera vez que se invoca `clasificar_con_groq`, no al importar el módulo. Así, si `GROQ_API_KEY` no está definida (por ejemplo, en un entorno donde solo se usa Ollama), la aplicación no se cae al arrancar: el error solo aparece, controlado, si el usuario intenta usar `groq` sin la clave configurada.

## Estructura del proyecto

```
triaje-llm-incidencias-urbanas/
├── app/
│   ├── main.py          # Endpoint FastAPI /triage y manejo de errores
│   ├── llm_service.py   # Clasificación con Ollama y Groq, extracción y validación del JSON
│   ├── prompts.py       # Prompt de sistema (ReAct/CoT + few-shot + reglas éticas)
│   ├── schemas.py       # Esquemas Pydantic de entrada y salida
│   ├── metrics.py       # Registro de tokens, coste estimado y latencia por petición
│   └── groq_client.py   # Prototipo inicial de cliente Groq (no usado por main.py; ver nota abajo)
├── dashboard/
│   └── app.py           # Interfaz Streamlit, clasifica llamando directamente a app/llm_service.py
├── tests/
│   ├── test_main.py         # Tests del endpoint FastAPI con mocking de Ollama
│   └── test_groq_client.py  # Tests del prototipo groq_client.py con mocking + 1 test de integración real
├── metrics.csv           # Historial de peticiones (se genera automáticamente)
├── requirements.txt
└── README.md
```

> **Nota sobre `app/groq_client.py`**: es un prototipo temprano de integración con Groq, con su propio prompt simplificado (categorías tipo `bache/alumbrado/basura`, sin ReAct). Quedó en el repositorio junto con sus tests (`test_groq_client.py`) como evidencia del proceso iterativo de desarrollo, pero **no lo usa `app/main.py`**: el endpoint y el dashboard usan exclusivamente `clasificar_con_groq` de `app/llm_service.py`, que sí implementa el prompt ReAct completo compartido con Ollama.

## Instalación

Requiere Python 3.12 y [Ollama](https://ollama.com/download) instalado localmente (solo necesario si quieres probar el proveedor local).

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

5. Copia `.env.example` a `.env` y añade tu clave real de Groq:

   ```
   GROQ_API_KEY=tu_clave_aqui
   ```

   Sin esta clave, el proveedor `ollama` sigue funcionando con normalidad; solo `groq` requiere la clave configurada.

## Ejecución

### Opción A: solo el dashboard (recomendada para uso normal)

El dashboard ya no depende de que el backend FastAPI esté corriendo: clasifica directamente llamando a la lógica de `app/llm_service.py`.

```powershell
streamlit run dashboard/app.py
```

Se abre automáticamente en `http://localhost:8501`. Antes de clasificar con `ollama`, asegúrate de que el servicio esté activo (cualquier comando de su CLI, como `ollama list`, lo levanta si estaba apagado).

### Opción B: backend FastAPI como servicio independiente

Para probar o documentar la API REST por separado (por ejemplo, con clientes externos o Swagger UI):

```powershell
uvicorn app.main:app --reload --reload-dir app
```

La API queda disponible en `http://127.0.0.1:8000`, con documentación interactiva en `http://127.0.0.1:8000/docs`.

> Se limita `--reload-dir` a la carpeta `app/` para evitar que cambios en `dashboard/` o `tests/` reinicien el backend a mitad de una petición en curso.

## Despliegue

El dashboard está publicado en Streamlit Community Cloud:

**[triaje-llm-incidencias-urbanas-luis.streamlit.app](https://triaje-llm-incidencias-urbanas-luis.streamlit.app/)**

En este entorno solo el proveedor **Groq** está disponible, porque Streamlit Cloud no ejecuta un servicio Ollama local. La clave `GROQ_API_KEY` se configura como *Secret* en el panel de administración de la app, nunca en el código ni en el repositorio. Seleccionar `ollama` en la versión desplegada devolverá un error controlado (503), ya que el servicio no es accesible desde ese entorno; la comparación completa entre ambos proveedores se demuestra en ejecución local.

## Ejemplo de uso (endpoint FastAPI)

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

El prompt de sistema (`app/prompts.py`), compartido por Ollama y Groq, combina:

- **ReAct**: el modelo debe generar explícitamente `Thought` → `Action` → `Observation` antes de la clasificación final tras la palabra clave `Answer:`.
- **Few-shot**: 3 ejemplos completos cubriendo distintas categorías y niveles de urgencia, para fijar el formato de salida.
- **Reglas éticas explícitas**: instrucción directa de ignorar género, origen, raza, nacionalidad, nivel económico o barrio al determinar la urgencia, basándola únicamente en el riesgo físico objetivo y la afluencia de la zona.

## Manejo de errores

La API y el dashboard capturan los mismos escenarios sin detener el servicio:

| Código / Estado | Causa |
|---|---|
| 502 | El modelo devolvió una respuesta mal formada (sin `Answer:`, JSON inválido, o claves faltantes) — `RespuestaLLMInvalida`. |
| 503 | No se pudo contactar con el servicio de Ollama, o falta `GROQ_API_KEY` para usar Groq — `ollama.ResponseError` / `ConnectionError`. |
| 422 | (Solo vía endpoint HTTP) El payload de entrada no cumple el esquema `IncidenciaInput` (validación de Pydantic). |

El dashboard traduce cada uno de estos casos en un mensaje legible para el operador, sin mostrar tracebacks. El endpoint FastAPI hace lo mismo mediante `HTTPException` con el código correspondiente.

## Registro de métricas

Cada petición, ya sea vía dashboard o vía endpoint, se registra en `metrics.csv` con: timestamp, proveedor, modelo, tokens de entrada/salida, coste estimado en USD, latencia en segundos y si tuvo éxito. La pestaña **Métricas** del dashboard permite filtrar por proveedor y visualizar latencia media y coste acumulado en gráficas comparativas, cumpliendo el requisito de comparación de coste/latencia/calidad entre el modelo local y el externo.

El rate limit de Groq se gestiona con reintentos y backoff exponencial (`tenacity`), hasta 4 intentos antes de propagar el error como `ConnectionError` controlado.

## Testing

```powershell
pytest -v
```

Los tests usan **mocking** para no depender de que los servicios reales estén corriendo:

**`tests/test_main.py`** (endpoint FastAPI, mocking sobre `ollama.chat`):

1. Respuesta válida del modelo → 200 con los campos estructurados.
2. Alucinación de estructura: falta la palabra clave `Answer:` → 502.
3. JSON con claves faltantes (`departamento` ausente) → 502.
4. Entrada inválida (falta el campo `texto`) → 422.

**`tests/test_groq_client.py`** (prototipo `groq_client.py`, mocking sobre el cliente de Groq):

- Validación de texto vacío, parseo de JSON, verificación de claves esperadas.
- Un test de integración real (`@pytest.mark.integration`), excluido del run normal, que sí llama a la API de Groq: `pytest -m integration`.

## Consideraciones éticas

El prompt del sistema instruye explícitamente al modelo para ignorar género, origen, raza, nacionalidad, nivel económico o barrio de la persona que reporta o de las personas afectadas al determinar la urgencia de una incidencia. La clasificación se basa exclusivamente en el riesgo físico objetivo descrito en el texto (tamaño del peligro, afluencia de la zona, tiempo transcurrido), evitando que el sistema perpetúe sesgos socioeconómicos o geográficos en la priorización de la atención ciudadana.

## Pendiente / próximos pasos

- Ampliar la comparación de calidad entre proveedores con un conjunto de incidencias de referencia etiquetadas manualmente.
- Persistir `metrics.csv` en una base de datos si el volumen de peticiones crece más allá de un archivo plano.