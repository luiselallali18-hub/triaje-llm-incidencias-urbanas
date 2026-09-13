"""
Tests para el cliente de Groq (app/groq_client.py).

Incluye dos grupos:
1. Tests con mock (rápidos, gratis, no llaman a la API real de Groq).
   Validan la lógica de clasificar_incidencia: validación de texto vacío,
   parseo de JSON, verificación de claves esperadas.
2. Un test de integración real, marcado con @pytest.mark.integration,
   que sí llama a la API real de Groq. Se excluye del run normal.

Uso:
    pytest                          -> corre solo los tests con mock
    pytest -m integration           -> corre solo el test de integración real
    pytest -m ""                    -> corre absolutamente todos
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.groq_client import clasificar_incidencia, CATEGORIAS_VALIDAS, URGENCIAS_VALIDAS


def _mock_respuesta_groq(contenido_json: dict):
    """Construye un objeto mock que imita la respuesta real del SDK de Groq."""
    mock_respuesta = MagicMock()
    mock_respuesta.choices = [MagicMock()]
    mock_respuesta.choices[0].message.content = json.dumps(contenido_json)
    return mock_respuesta


class TestClasificarIncidenciaConMock:
    """Tests que no llaman a la API real de Groq: usan un mock del cliente."""

    def test_texto_vacio_lanza_error(self):
        with pytest.raises(ValueError, match="no puede estar vacío"):
            clasificar_incidencia("")

    def test_texto_solo_espacios_lanza_error(self):
        with pytest.raises(ValueError, match="no puede estar vacío"):
            clasificar_incidencia("   ")

    @patch("app.groq_client.client")
    def test_respuesta_valida_devuelve_diccionario_correcto(self, mock_client):
        mock_client.chat.completions.create.return_value = _mock_respuesta_groq(
            {
                "categoria": "alumbrado",
                "urgencia": "alta",
                "resumen": "Farola apagada en la esquina.",
            }
        )

        resultado = clasificar_incidencia("No funciona la farola de mi calle")

        assert resultado["categoria"] == "alumbrado"
        assert resultado["urgencia"] == "alta"
        assert resultado["resumen"] == "Farola apagada en la esquina."

    @patch("app.groq_client.client")
    def test_categoria_esta_dentro_de_las_validas(self, mock_client):
        mock_client.chat.completions.create.return_value = _mock_respuesta_groq(
            {"categoria": "bache", "urgencia": "media", "resumen": "Bache grande."}
        )

        resultado = clasificar_incidencia("Hay un bache enorme")

        assert resultado["categoria"] in CATEGORIAS_VALIDAS
        assert resultado["urgencia"] in URGENCIAS_VALIDAS

    @patch("app.groq_client.client")
    def test_json_invalido_lanza_error(self, mock_client):
        mock_respuesta = MagicMock()
        mock_respuesta.choices = [MagicMock()]
        mock_respuesta.choices[0].message.content = "esto no es json"
        mock_client.chat.completions.create.return_value = mock_respuesta

        with pytest.raises(ValueError, match="no devolvió un JSON válido"):
            clasificar_incidencia("Texto de prueba")

    @patch("app.groq_client.client")
    def test_faltan_claves_lanza_error(self, mock_client):
        mock_client.chat.completions.create.return_value = _mock_respuesta_groq(
            {"categoria": "ruido"}
        )

        with pytest.raises(ValueError, match="Faltan claves"):
            clasificar_incidencia("Hay mucho ruido por la noche")


@pytest.mark.integration
class TestClasificarIncidenciaIntegracionReal:
    """
    Test de integración real: llama de verdad a la API de Groq.
    Excluido del run normal de pytest. Ejecutar solo con:
        pytest -m integration
    """

    def test_llamada_real_a_groq_devuelve_formato_esperado(self):
        resultado = clasificar_incidencia(
            "Hay un contenedor de basura desbordado desde hace una semana"
        )

        assert resultado["categoria"] in CATEGORIAS_VALIDAS
        assert resultado["urgencia"] in URGENCIAS_VALIDAS
        assert isinstance(resultado["resumen"], str)
        assert len(resultado["resumen"]) > 0