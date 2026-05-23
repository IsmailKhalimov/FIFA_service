import streamlit as st
from login import login_user
from register import register_user


def login_page():
    st.title("Авторизация")

    with st.form("login_form"):
        username = st.text_input("Имя пользователя")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

        if submitted:
            login_result = login_user(username, password)
            if login_result["status"] == "Авторизация успешна.":
                st.success("Добро пожаловать!")
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["role"] = login_result["role"]
                st.rerun()
            else:
                st.error(login_result["status"])


def register_page():
    st.title("Регистрация")

    with st.form("register_form"):
        username = st.text_input("Имя пользователя")
        password = st.text_input("Пароль", type="password")
        role = st.selectbox("Роль:", ['Обычный пользователь', "Журналист", "Администратор"])
        submitted = st.form_submit_button("Зарегистрироваться")

        if submitted:
            register_result = register_user(username, password, role)
            if register_result == "Регистрация успешна.":
                st.success("Регистрация прошла успешно! Теперь вы можете войти в систему.")
            else:
                st.error(register_result)
