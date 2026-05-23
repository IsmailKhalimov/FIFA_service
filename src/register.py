import psycopg2
from db_connection import get_db_connection
from werkzeug.security import generate_password_hash


def register_user(username, password, role="user"):
    if role == "Журналист":
        role = "reporter"
    elif role == "Администратор":
        role = "admin"
    else:
        role = "user"
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        conn.close()
        return "Пользователь с таким именем уже существует."

    hashed_password = generate_password_hash(password)

    query_insert = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
    cursor.execute(query_insert, (username, hashed_password, role))

    conn.commit()
    conn.close()
    return "Регистрация успешна."
