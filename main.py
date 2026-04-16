import json
import os

import streamlit as st
from dotenv import load_dotenv
from lxml import etree
from openai import OpenAI
from pandas import read_csv

from prompt import general_prompt, stronger_prompt
from utils.classifier import contruir_poliza_eg, get_clasificar_xmls
from utils.xml_parser import parse_cfdi


def stream_assistant_answer(client, model, conversation):
    """
    Llama al modelo con stream=True y pinta la respuesta progresivamente.
    Devuelve el texto completo generado.
    """
    full_response = ""
    placeholder = st.empty()

    stream = client.chat.completions.create(
        model=model,
        messages=conversation,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            full_response += delta.content
            placeholder.markdown(full_response)

    return full_response


load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

client_openai = OpenAI(api_key=OPENAI_API_KEY)
client_google = OpenAI(api_key=GOOGLE_API_KEY, base_url=GEMINI_BASE_URL)
client_groq = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

model_openai = "gpt-5.4-mini"
model_deepseek = "deepseek-chat"
model_groq = "llama-3.3-70b-versatile"
model_google = "gemini-2.5-flash"


st.set_page_config(page_title="Cont-AI", layout="wide")
st.title("👩‍💻 Cont-AI")
st.caption("Auxiliar contable")

st.markdown(
    """
    Herramienta de inteligencia artificial diseñada para automatizar la clasificación de cuentas contables a partir de archivos XML-CFDI

    puede comenzar agregando sus xml a la barra de la derecha y si tiene una duda de estos puede usar el asistente 
    """
)

if "cfdi_data" not in st.session_state:
    st.session_state.cfdi_data = None


if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "¿En qué te puedo ayudar?"}
    ]

if "clasificacion" not in st.session_state:
    st.session_state.clasificacion = []

if "catalogo" not in st.session_state:
    df = read_csv(r"utils\catalogo contable.csv")
    st.session_state.catalogo = df

section_choice = "chat"

with st.sidebar:
    section_choice = st.radio("Secciones", ["Chat", "Dudas generales"], index=0)
    if section_choice == "Chat":
        st.subheader("Cargar archivos xml")
        xml = st.file_uploader("Archivo XML", type=["xml"], accept_multiple_files=True)

        if xml:
            st.session_state.cfdi_data = parse_cfdi(xml)

    elif section_choice == "Dudas generales":
        st.write("Aqui podras preguntar sobre dudas referentes a la contabilidad")


if section_choice == "Chat":
    # ---------------------------
    # TABS PRINCIPALES
    # ---------------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        ["💬 Asistente", "🔎 Vista CFDI", "📊 Poliza", "📊 Catalogo de Cuenta Contable"]
    )

    with tab1:
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                message_block = st.chat_message(msg["role"])
                message_block.write(msg["content"])

        user_prompt = None

        if text_prompt := st.chat_input(placeholder="Escribe tu mensaje aquí..."):
            user_prompt = text_prompt

        if user_prompt:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            st.chat_message("user").write(user_prompt)
            if st.session_state.cfdi_data is not None:
                conversation = [
                    {"role": "system", "content": stronger_prompt},
                    {
                        "role": "system",
                        "content": f"CFDI cargado:\n{st.session_state.cfdi_data}",
                    },
                    {
                        "role": "system",
                        "content": f"Cuentas predichas:\n{st.session_state.clasificacion}",
                    },
                    {
                        "role": "system",
                        "content": f"Catalogo contable que se cuenta:\n{st.session_state.catalogo}",
                    },
                ]
            else:
                conversation = [{"role": "system", "content": stronger_prompt}]
            conversation.extend(
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            )

            done = False

            while not done:
                completion = client_openai.chat.completions.create(
                    model=model_openai,
                    messages=conversation,
                )
                choice = completion.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason

                last_non_stream_response = message.content or ""
                done = True

            with st.chat_message("assistant"):
                response = stream_assistant_answer(
                    client=client_openai,
                    model=model_openai,
                    conversation=conversation,
                )

            st.session_state.messages.append({"role": "assistant", "content": response})

    # ---------------------------
    # TAB 2 - VISTA CFDI
    # ---------------------------
    with tab2:
        if st.session_state.cfdi_data is not None:
            st.subheader("Resumen del CFDI")
            st.write(st.session_state.cfdi_data)
        else:
            st.write("Carga un XML.")
    # ---------------------------
    # TAB 3 - Armado de poliza
    # ---------------------------
    with tab3:
        if st.session_state.cfdi_data is not None:
            df = st.session_state.cfdi_data
            df = df[df["Estado SAT"] == "Vigente"]

            for _, row in df.iterrows():
                cuenta_predicha = get_clasificar_xmls(row)
                st.subheader("Póliza preliminar sugerida")
                poliza = contruir_poliza_eg(
                    row, cuenta_predicha, st.session_state.catalogo
                )
                aux = (
                    cuenta_predicha[:4]
                    + "."
                    + cuenta_predicha[4:7]
                    + "."
                    + cuenta_predicha[-4:]
                )
                st.session_state.clasificacion.append((row, aux))

                st.write(poliza)

        else:
            st.write("No has cargado ningun xml")

    with tab4:
        # Mostrar el catálogo
        st.write(st.session_state.catalogo)

elif section_choice == "Dudas generales":
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            message_block = st.chat_message(msg["role"])
            message_block.write(msg["content"])

    user_prompt = None

    if text_prompt := st.chat_input(placeholder="Escribe tu duda aquí..."):
        user_prompt = text_prompt

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        st.chat_message("user").write(user_prompt)
        if st.session_state.cfdi_data is not None:
            conversation = [
                {"role": "assistant", "content": general_prompt},
            ]
        else:
            conversation = [{"role": "assistant", "content": general_prompt}]
        conversation.extend(
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages
        )

        done = False

        while not done:
            completion = client_google.chat.completions.create(
                model=model_google,
                messages=conversation,
            )
            choice = completion.choices[0]
            message = choice.message

            last_non_stream_response = message.content or ""
            done = True

        with st.chat_message("assistant"):
            response = stream_assistant_answer(
                client=client_google,
                model=model_google,
                conversation=conversation,
            )

        st.session_state.messages.append({"role": "assistant", "content": response})
