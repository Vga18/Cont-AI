import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from prompt import stronger_prompt

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

client_openai = OpenAI(api_key=OPENAI_API_KEY)
client_google = OpenAI(api_key=GOOGLE_API_KEY, base_url=GEMINI_BASE_URL)

model_openai = "gpt-5.4-mini"
model_deepseek = "deepseek-chat"
model_groq = "llama-3.3-70b-versatile"
model_google = "gemini-2.5-flash"


st.title("👩‍💻 Cont-AI")
st.caption("Auxiliar contable")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¿En qué te puedo ayudar?"}
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Escribe tu mensaje aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    conversation = [{"role": "assistant", "content": stronger_prompt}]
    conversation.extend(
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    )

    with st.chat_message("assistant"):
        stream = client_google.chat.completions.create(
            model=model_google, messages=conversation, stream=True
        )
        response = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": response})
