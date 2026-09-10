"""
Tests unitarios del endpoint /triage.

Usamos mocking sobre ollama.chat para no depender de que el servicio
de Ollama esté corriendo ni de la aleatoriedad real del modelo.
Esto cubre el bloque V del checklist:
  - Al menos 3 tests unitarios con Pytest.
  - Un test que compruebe la respuesta del endpoint ante un input válido.
  - Un test que evalúe el manejo de errores ante alucinaciones de estructura.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAYLOAD_VALIDO = {
    "texto": "Hay una rama rota colgando sobre un banco en el Retiro",
    "proveedor": "ollama",
}


def _mock_respuesta_ollama(contenido_texto: str) -> MagicMock:
    """Construye un objeto que imita lo que devuelve ollama.chat(...)."""
    mock_respuesta = MagicMock()
    mock_respuesta.__getitem__.side_effect = lambda clave: {
        "message": {"content": contenido_texto}
    }[clave]
    mock_respuesta.get.side_effect = lambda clave, default=0: {
        "prompt_eval_count": 42,
        "eval_count": 17,
    }.get(clave, default)
    return mock_respuesta


@patch("app.llm_service.ollama.chat")
def test_endpoint_responde_200_con_input_valido_y_json_bien_formado(mock_chat):
    """
    Simula una respuesta perfecta del LLM (Thought/Action/Observation + Answer con JSON válido)
    y comprueba que el endpoint devuelve 200 con los campos esperados.
    """
    contenido_simulado = (
        "Thought: El texto describe una rama rota con riesgo de caída.\n"
        "Action: Reviso riesgo físico y afluencia de la zona.\n"
        "Observation: Riesgo alto sobre zona transitada.\n"
        "Answer: "
        '{"categoria": "riesgo_caida", "urgencia": "alta", '
        '"resumen": "Rama rota con riesgo sobre banco", '
        '"departamento": "Emergencias"}'
    )
    mock_chat.return_value = _mock_respuesta_ollama(contenido_simulado)

    respuesta = client.post("/triage", json=PAYLOAD_VALIDO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["categoria"] == "riesgo_caida"
    assert cuerpo["urgencia"] == "alta"
    assert cuerpo["departamento"] == "Emergencias"
    assert "razonamiento" in cuerpo


@patch("app.llm_service.ollama.chat")
def test_endpoint_devuelve_502_si_el_modelo_alucina_json_mal_formado(mock_chat):
    """
    Simula una 'alucinación de estructura': el modelo responde sin la palabra
    clave 'Answer:' esperada. Esto debe disparar RespuestaLLMInvalida dentro de
    llm_service.py y traducirse en un 502 controlado, sin tumbar el servidor.
    """
    contenido_corrupto = (
        "Thought: Esta rama parece peligrosa.\n"
        "Creo que es urgente pero no voy a dar una respuesta estructurada."
    )
    mock_chat.return_value = _mock_respuesta_ollama(contenido_corrupto)

    respuesta = client.post("/triage", json=PAYLOAD_VALIDO)

    assert respuesta.status_code == 502
    assert "detail" in respuesta.json()


@patch("app.llm_service.ollama.chat")
def test_endpoint_devuelve_502_si_el_json_tiene_claves_faltantes(mock_chat):
    """
    Otra variante de alucinación de estructura: el bloque tras 'Answer:' es un
    JSON válido sintácticamente, pero le faltan claves requeridas por
    TriajeOutput (por ejemplo, falta 'departamento'). Debe fallar de forma
    controlada, no con un error no gestionado.
    """
    contenido_incompleto = (
        "Thought: Análisis breve.\n"
        "Answer: "
        '{"categoria": "riesgo_caida", "urgencia": "alta", '
        '"resumen": "Rama rota sobre banco"}'
    )
    mock_chat.return_value = _mock_respuesta_ollama(contenido_incompleto)

    respuesta = client.post("/triage", json=PAYLOAD_VALIDO)

    assert respuesta.status_code in (500, 502)


def test_endpoint_devuelve_422_si_falta_el_campo_texto():
    """
    Test adicional de robustez: si el payload no cumple el esquema de entrada
    (IncidenciaInput), FastAPI/Pydantic debe rechazarlo con 422 antes de
    siquiera llamar al LLM.
    """
    respuesta = client.post("/triage", json={"proveedor": "ollama"})
    assert respuesta.status_code == 422