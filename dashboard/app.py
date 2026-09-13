"""
Dashboard de triaje de incidencias urbanas.

Interfaz Human-in-the-loop: el operador introduce el texto de una
incidencia, la envía al backend de FastAPI, y revisa tanto el resultado
estructurado (categoría, urgencia, departamento, resumen) como el
razonamiento completo del LLM antes de validar la clasificación.
"""

import requests
import streamlit as st
import pandas as pd
import os

URL_API = "http://127.0.0.1:8000/triage"

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
                    "El servicio de LLM no está disponible ahora mismo. "
                    "Verifica que el proveedor esté corriendo."
                )

            elif respuesta.status_code == 422:
                st.error("Datos de entrada inválidos. Revisa el formulario.")

            else:
                st.error(f"Error inesperado (código {respuesta.status_code}).")

with tab_metricas:
    st.header("📊 Métricas de uso")
    st.caption("Historial de peticiones al motor de triaje")

    # Ruta del CSV de métricas (en la raíz del proyecto)
    ruta_metrics = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")
    
    if not os.path.exists(ruta_metrics):
        st.warning("No se encontró el archivo metrics.csv. Asegúrate de que el backend esté registrando las peticiones.")
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

