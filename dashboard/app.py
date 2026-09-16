"""
Dashboard de triaje de incidencias urbanas.

Interfaz Human-in-the-loop: el operador introduce el texto de una
incidencia, la clasifica mediante el mismo motor de triaje que expone
la API de FastAPI, y revisa tanto el resultado estructurado (categoria,
urgencia, departamento, resumen) como el razonamiento completo del LLM
antes de validar la clasificacion.
"""

import os
import sys
import time
from pathlib import Path

import ollama
import pandas as pd
import streamlit as st

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from app.llm_service import (
    clasificar_con_groq,
    clasificar_con_ollama,
    RespuestaLLMInvalida,
)
from app.metrics import registrar_peticion

COLOR_URGENCIA = {
    "alta": "🔴",
    "media": "🟠",
    "baja": "🟢",
}

st.set_page_config(
    page_title="Triaje de Incidencias Urbanas",
    page_icon="🌳",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            linear-gradient(rgba(245, 250, 247, 0.35), rgba(245, 250, 247, 0.35)),
            url("https://images.unsplash.com/photo-1519331379826-f10be5486c6f?auto=format&fit=crop&w=1920&q=80");
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    h1, h2, h3, p, label, .stMarkdown, .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.78);
        border-radius: 6px;
        padding: 3px 8px;
        width: fit-content;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
    }

    h1 {
        padding: 6px 12px;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 6px 12px;
    }
</style>
    """,
    unsafe_allow_html=True,
)

st.title("🌳 Motor de Triaje de Incidencias Urbanas")
st.caption(
    "Introduce el texto libre de una incidencia ciudadana. "
    "El modelo clasificará la urgencia y el departamento responsable."
)

# Pestañas: Triaje y Métricas
tab_triage, tab_metricas = st.tabs(["Triaje", "Métricas"])

with tab_triage:
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
                inicio = time.perf_counter()
                error_codigo = None
                detalle_error = None
                datos = None

                try:
                    if proveedor == "groq":
                        resultado, metadatos = clasificar_con_groq(texto_incidencia)
                    else:
                        resultado, metadatos = clasificar_con_ollama(texto_incidencia)

                    registrar_peticion(
                        proveedor=metadatos["proveedor"],
                        modelo=metadatos["modelo"],
                        tokens_entrada=metadatos["tokens_entrada"],
                        tokens_salida=metadatos["tokens_salida"],
                        latencia_segundos=metadatos["latencia_segundos"],
                        exito=True,
                    )
                    datos = resultado.model_dump(mode="json")

                except RespuestaLLMInvalida as error:
                    registrar_peticion(
                        proveedor=proveedor,
                        modelo="desconocido",
                        tokens_entrada=0,
                        tokens_salida=0,
                        latencia_segundos=time.perf_counter() - inicio,
                        exito=False,
                    )
                    error_codigo = 502
                    detalle_error = str(error)

                except (ollama.ResponseError, ConnectionError) as error:
                    registrar_peticion(
                        proveedor=proveedor,
                        modelo="desconocido",
                        tokens_entrada=0,
                        tokens_salida=0,
                        latencia_segundos=time.perf_counter() - inicio,
                        exito=False,
                    )
                    error_codigo = 503
                    detalle_error = str(error)

            if datos is not None:
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

            elif error_codigo == 502:
                st.error(
                    "El modelo devolvió una respuesta con formato incorrecto "
                    "(alucinación de estructura). Detalle: "
                    f"{detalle_error}"
                )

            elif error_codigo == 503:
                st.error(
                    "El servicio de LLM no está disponible ahora mismo. "
                    "Verifica que el proveedor esté corriendo. Detalle: "
                    f"{detalle_error}"
                )

with tab_metricas:
    st.header("📊 Métricas de uso")
    st.caption("Historial de peticiones al motor de triaje")

    # Ruta del CSV de métricas (en la raíz del proyecto)
    ruta_metrics = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")

    if not os.path.exists(ruta_metrics):
        st.warning("No se encontró el archivo metrics.csv. Asegúrate de que se hayan registrado peticiones.")
    else:
        df = pd.read_csv(ruta_metrics)

        # Filtro por proveedor
        filtro_proveedor = st.selectbox(
            "Filtrar por proveedor",
            options=["todos", "ollama", "groq"]
        )

        if filtro_proveedor != "todos":
            df_filtrado = df[df["proveedor"] == filtro_proveedor].copy()
        else:
            df_filtrado = df.copy()

        # Mostrar tabla
        st.subheader("Últimas peticiones")
        st.dataframe(
            df_filtrado.sort_values("timestamp", ascending=False).head(50),
            use_container_width=True,
            hide_index=True,
        )

        # Gráficas de comparación
        st.subheader("Comparativa por proveedor")

        if not df_filtrado.empty:
            col1, col2 = st.columns(2)

            # Latencia media por proveedor
            latencia_media = df_filtrado.groupby("proveedor")["latencia_segundos"].mean().reset_index()
            with col1:
                st.bar_chart(latencia_media.set_index("proveedor"), y_label="Latencia media (s)")

            # Coste acumulado por proveedor
            coste_acumulado = df_filtrado.groupby("proveedor")["coste_estimado_usd"].sum().reset_index()
            with col2:
                st.bar_chart(coste_acumulado.set_index("proveedor"), y_label="Coste acumulado (USD)")

            # Stats adicionales
            st.subheader("Estadísticas")
            col3, col4, col5 = st.columns(3)
            with col3:
                st.metric("Total peticiones", len(df_filtrado))
            with col4:
                st.metric("Tasa de éxito", f"{(df_filtrado['exito'] == True).mean() * 100:.1f}%")
            with col5:
                st.metric("Coste total", f"${df_filtrado['coste_estimado_usd'].sum():.4f}")
        else:
            st.info("Aún no hay datos registrados en el CSV de métricas.")