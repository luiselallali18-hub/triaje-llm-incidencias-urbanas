"""
Dashboard de triaje de incidencias urbanas.

Interfaz Human-in-the-loop: el operador introduce el texto de una
incidencia, la envía al backend de FastAPI, y revisa tanto el resultado
estructurado (categoría, urgencia, departamento, resumen) como el
razonamiento completo del LLM antes de validar la clasificación.
"""

import requests
import streamlit as st

URL_API = "http://127.0.0.1:8000/triage"

COLOR_URGENCIA = {
    "alta": "🔴",
    "media": "🟠",
    "baja": "🟢",
}

st.set_page_config(
    page_title="Triaje de Incidencias Urbanas",
    page_icon="🌳",
    layout="centered",
)

st.title("🌳 Motor de Triaje de Incidencias Urbanas")
st.caption(
    "Introduce el texto libre de una incidencia ciudadana. "
    "El modelo clasificará la urgencia y el departamento responsable."
)

with st.form("formulario_incidencia"):
    texto_incidencia = st.text_area(
        "Descripción de la incidencia",
        placeholder="Ej: Hay una rama rota colgando sobre un banco en el Retiro",
        height=120,
    )
    proveedor = st.selectbox("Proveedor del modelo", options=["ollama", "groq"])
    enviado = st.form_submit_button("Clasificar incidencia")

if enviado:
    if not texto_incidencia.strip():
        st.warning("Escribe una descripción antes de clasificar.")
    else:
        with st.spinner("El modelo está analizando la incidencia..."):
            try:
                respuesta = requests.post(
                    URL_API,
                    json={"texto": texto_incidencia, "proveedor": proveedor},
                    timeout=180,
                )
            except requests.exceptions.ConnectionError:
                st.error(
                    "No se pudo conectar con la API. "
                    "Comprueba que el servidor FastAPI esté corriendo en "
                    "http://127.0.0.1:8000."
                )
                st.stop()

        if respuesta.status_code == 200:
            datos = respuesta.json()
            emoji_urgencia = COLOR_URGENCIA.get(datos["urgencia"], "⚪")

            st.success("Incidencia clasificada correctamente")

            columna_1, columna_2 = st.columns(2)
            with columna_1:
                st.metric("Categoría", datos["categoria"])
                st.metric("Departamento", datos["departamento"])
            with columna_2:
                st.metric("Urgencia", f"{emoji_urgencia} {datos['urgencia']}")

            st.subheader("Resumen")
            st.write(datos["resumen"])

            with st.expander("Ver razonamiento del modelo (Thought / Action / Observation)"):
                st.text(datos["razonamiento"])

        elif respuesta.status_code == 502:
            st.error(
                "El modelo devolvió una respuesta con formato incorrecto "
                "(alucinación de estructura). Detalle: "
                f"{respuesta.json().get('detail', 'sin detalle')}"
            )

        elif respuesta.status_code == 503:
            st.error(
                "El servicio de Ollama no está disponible ahora mismo. "
                "Verifica que esté corriendo."
            )

        elif respuesta.status_code == 422:
            st.error("Datos de entrada inválidos. Revisa el formulario.")

        else:
            st.error(f"Error inesperado (código {respuesta.status_code}).")
