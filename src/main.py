import streamlit as st
from auth import login_page, register_page
from pages import main_page

st.set_page_config(page_title="Football Club Database", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.session_state["role"] = None

if st.session_state["logged_in"]:
    main_page(st.session_state['role'])
else:
    st.sidebar.title("Навигация")
    auth_page = st.sidebar.radio("Действие", ("Войти", "Регистрация"))
    if auth_page == "Войти":
        login_page()
    elif auth_page == "Регистрация":
        register_page()
