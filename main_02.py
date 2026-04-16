import os
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from openpyxl import Workbook
from pandas import concat, read_csv

from prompt import general_prompt, stronger_prompt
from utils.classifier import contruir_poliza_eg, get_clasificar_xmls
from utils.xml_parser import parse_cfdi

# ============================
# CONFIGURACIÓN INICIAL
# ============================

st.set_page_config(page_title="Cont-AI", layout="wide")
st.title("👩‍💻 Cont-AI")
st.caption("Auxiliar contable inteligente")

load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

client_openai = OpenAI(api_key=OPENAI_API_KEY)
client_google = OpenAI(api_key=GOOGLE_API_KEY, base_url=GEMINI_BASE_URL)

model_openai = "gpt-5.4-mini"
model_google = "gemini-2.5-flash"


# ============================
# FUNCIONES
# ============================


def stream_assistant_answer(client, model, conversation):
    full_response = ""
    placeholder = st.empty()

    stream = client.chat.completions.create(
        model=model,
        messages=conversation,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and getattr(delta, "content", None):
                full_response += delta.content
                placeholder.markdown(full_response)

    return full_response


def build_conversation(system_prompt, messages, extra_context=None, max_messages=6):
    """
    Construye conversación controlando tamaño de contexto.
    Solo envía los últimos N mensajes.
    """
    conversation = [{"role": "system", "content": system_prompt}]

    if extra_context:
        conversation.append(
            {"role": "system", "content": f"Contexto adicional:\n{extra_context}"}
        )

    trimmed_messages = messages[-max_messages:]
    conversation.extend(trimmed_messages)

    return conversation


def generar_excel_desde_df(df):
    wb = Workbook()
    ws = wb.active
    ws.title = "Poliza"

    # Encabezados
    ws.append(list(df.columns))

    # Filas
    for _, row in df.iterrows():
        ws.append(row.tolist())

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ============================
# SESSION STATE
# ============================

if "cfdi_data" not in st.session_state:
    st.session_state.cfdi_data = None

if "chat_cfdi_messages" not in st.session_state:
    st.session_state.chat_cfdi_messages = [
        {"role": "assistant", "content": "¿En qué te puedo ayudar?"}
    ]

if "chat_general_messages" not in st.session_state:
    st.session_state.chat_general_messages = [
        {"role": "assistant", "content": "¿Cuál es tu duda contable?"}
    ]

if "clasificacion" not in st.session_state:
    st.session_state.clasificacion = []

if "catalogo" not in st.session_state:
    st.session_state.catalogo = read_csv(os.path.join("utils", "catalogo contable.csv"))


# ============================
# SIDEBAR
# ============================

with st.sidebar:
    section_choice = st.radio("Secciones", ["Chat CFDI", "Dudas generales"])

    if section_choice == "Chat CFDI":
        st.subheader("Cargar archivos XML")
        xml = st.file_uploader(
            "Archivo XML",
            type=["xml"],
            accept_multiple_files=True,
        )

        if xml:
            st.session_state.cfdi_data = parse_cfdi(xml)

    else:
        st.write("Consulta dudas generales de contabilidad mexicana.")


# ============================
# SECCIÓN 1 - CHAT CFDI
# ============================

if section_choice == "Chat CFDI":
    tab1, tab2, tab3, tab4 = st.tabs(
        ["💬 Asistente", "🔎 Vista CFDI", "📊 Póliza", "📘 Catálogo"]
    )

    # ---------------------------
    # TAB 1 - CHAT
    # ---------------------------

    with tab1:
        for msg in st.session_state.chat_cfdi_messages:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Escribe tu mensaje..."):
            st.session_state.chat_cfdi_messages.append(
                {"role": "user", "content": prompt}
            )
            st.chat_message("user").write(prompt)

            extra_context = None
            if st.session_state.cfdi_data is not None:
                extra_context = f"""
                CFDI:
                {st.session_state.cfdi_data.head(3)}

                Clasificaciones:
                {st.session_state.clasificacion}
                
                Catalago:
                {st.session_state.catalogo}
                """

            conversation = build_conversation(
                stronger_prompt,
                st.session_state.chat_cfdi_messages,
                extra_context=extra_context,
            )

            with st.chat_message("assistant"):
                response = stream_assistant_answer(
                    client_openai,
                    model_openai,
                    conversation,
                )

            st.session_state.chat_cfdi_messages.append(
                {"role": "assistant", "content": response}
            )

    # ---------------------------
    # TAB 2 - VISTA CFDI
    # ---------------------------

    with tab2:
        if st.session_state.cfdi_data is not None:
            st.subheader("Resumen del CFDI")
            st.dataframe(st.session_state.cfdi_data)
        else:
            st.info("Carga un XML.")

    # ---------------------------
    # TAB 3 - PÓLIZA
    # ---------------------------

    with tab3:
        if st.session_state.cfdi_data is not None:
            df = st.session_state.cfdi_data
            df = df[df["Estado SAT"] == "Vigente"]

            if df.empty:
                st.info("No hay CFDI vigentes.")
            else:
                st.subheader("Configuración de póliza")

                # 🟢 Opción para unir pólizas
                unir_polizas = st.checkbox(
                    "Unir todas las facturas seleccionadas en una sola póliza"
                )

                # 🟢 Selector de facturas
                df["Factura_ID"] = (
                    df["Serie"].astype(str)
                    + "-"
                    + df["Folio"].astype(str)
                    + " | "
                    + df["Nombre Emisor"].astype(str)
                )

                facturas_seleccionadas = st.multiselect(
                    "Selecciona las facturas a procesar:",
                    options=df["Factura_ID"].tolist(),
                    default=df["Factura_ID"].tolist(),
                )

                df_filtrado = df[df["Factura_ID"].isin(facturas_seleccionadas)]

                if df_filtrado.empty:
                    st.warning("No seleccionaste facturas.")
                else:
                    st.session_state.clasificacion = []
                    polizas_generadas = []

                    for _, row in df_filtrado.iterrows():
                        cuenta_predicha = get_clasificar_xmls(row)

                        poliza = contruir_poliza_eg(
                            row,
                            cuenta_predicha,
                            st.session_state.catalogo,
                        )

                        aux = (
                            cuenta_predicha[:4]
                            + "."
                            + cuenta_predicha[4:7]
                            + "."
                            + cuenta_predicha[-4:]
                        )

                        st.session_state.clasificacion.append(aux)
                        polizas_generadas.append(poliza)

                    # ============================
                    # 🔵 MODO NORMAL (una por una)
                    # ============================
                    if not unir_polizas:
                        for poliza in polizas_generadas:
                            st.subheader("Póliza preliminar sugerida")
                            st.dataframe(poliza)

                    # ============================
                    # 🔵 MODO CONSOLIDADO
                    # ============================
                    else:
                        st.subheader("Póliza consolidada")

                        poliza_global = (
                            concat(polizas_generadas)
                            .groupby(
                                ["NUM_CTA", "CONCEPTO", "CARGO_ABONO"], as_index=False
                            )
                            .agg(
                                {
                                    "Monto": "sum",
                                    "NOMBRE_POL": "first",
                                }
                            )
                        )

                        st.dataframe(poliza_global)
                        excel_file = generar_excel_desde_df(poliza_global)

                        st.download_button(
                            label="📥 Descargar póliza en Excel",
                            data=excel_file,
                            file_name="poliza.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
        else:
            st.warning("No has cargado ningún XML.")

    # ---------------------------
    # TAB 4 - CATÁLOGO
    # ---------------------------

    with tab4:
        st.dataframe(st.session_state.catalogo)


# ============================
# SECCIÓN 2 - DUDAS GENERALES
# ============================

else:
    for msg in st.session_state.chat_general_messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Escribe tu duda contable..."):
        st.session_state.chat_general_messages.append(
            {"role": "user", "content": prompt}
        )
        st.chat_message("user").write(prompt)

        conversation = build_conversation(
            general_prompt,
            st.session_state.chat_general_messages,
        )

        with st.chat_message("assistant"):
            response = stream_assistant_answer(
                client_google,
                model_google,
                conversation,
            )

        st.session_state.chat_general_messages.append(
            {"role": "assistant", "content": response}
        )
