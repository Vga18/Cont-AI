import json
import os

import streamlit as st
from dotenv import load_dotenv
from lxml import etree
from openai import OpenAI

from prompt import stronger_prompt
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
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
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
    Usa el panel lateral para alternar entre el chatr.
    """
)

if "cfdi_data" not in st.session_state:
    st.session_state.cfdi_data = None


if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "¿En qué te puedo ayudar?"}
    ]

if "clasificacion" not in st.session_state:
    st.session_state.clasificacion = None

section_choice = "Chat"

with st.sidebar:
    section_choice = st.radio("Secciones", ["Chat", "Calculadora ISR"], index=0)
    if section_choice == "Chat":
        st.subheader("Cargar archivos xml")
        xml = st.file_uploader("Archivo XML", type=["xml"], accept_multiple_files=True)

        if xml:
            st.session_state.cfdi_data = parse_cfdi(xml)

    elif section_choice == "Calculadora ISR":
        st.subheader("Calculadora")


if section_choice == "Chat":
    # ---------------------------
    # TABS PRINCIPALES
    # ---------------------------
    tab1, tab2, tab3 = st.tabs(["💬 Asistente", "🔎 Vista CFDI", "📊 Poliza"])

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
                ]
            else:
                conversation = [{"role": "system", "content": stronger_prompt}]
            conversation.extend(
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            )

            done = False

            while not done:
                completion = client_groq.chat.completions.create(
                    model=model_groq,
                    messages=conversation,
                    # tools=tools,
                )
                choice = completion.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason

                if finish_reason == "tool_calls" and message.tool_calls:
                    tool_calls = message.tool_calls
                    tool_calls_serialized = [
                        {
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                            "type": tc.type,
                        }
                        for tc in tool_calls
                    ]
                    # results = handle_tool_calls(tool_calls)
                    # safe_content = message.content or ""
                    # if safe_content:
                    #     st.session_state.messages.append({"role": message.role, "content": safe_content})
                    # conversation.append(
                    #     {
                    #         "role": message.role,
                    #         "content": safe_content,
                    #         "tool_calls": tool_calls_serialized,
                    #     }
                    # )
                    # conversation.extend(results)
                    continue

                last_non_stream_response = message.content or ""
                done = True

            with st.chat_message("assistant"):
                response = stream_assistant_answer(
                    client=client_groq,
                    model=model_groq,
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

                poliza = contruir_poliza_eg(row, cuenta_predicha)

                st.write(poliza)

        else:
            st.write("No has cargado ningun xml")

elif section_choice == "Calculadora ISR":
    st.divider()
    with st.expander("Comparativa de compañías", expanded=True):
        pass
