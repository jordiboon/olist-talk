import streamlit as st

from olist_talk import obs, pipeline

st.set_page_config(page_title="Olist Talk")
obs.setup()

st.markdown("<style>header[data-testid='stHeader'] {display: none;}</style>", unsafe_allow_html=True)

st.title("Talk to the Olist data")

# per browser session only: gone on refresh, never written anywhere
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if question := st.chat_input("Ask a question about the orders and reviews"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Working..."):
            trace = pipeline.answer(question)
        reply = f"Something went wrong: {trace.error}" if trace.error else trace.answer
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
