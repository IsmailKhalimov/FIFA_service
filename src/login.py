import psycopg2
from db_connection import get_db_connection
from werkzeug.security import check_password_hash


def login_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT password, role FROM Users WHERE username = %s"
    cursor.execute(query, (username,))
    result = cursor.fetchone()
    conn.close()

    if result:
        hashed_password = result[0]
        if check_password_hash(hashed_password, password):
            return {"status": "Авторизация успешна.", "role": result[1]}
        else:
            return {"status": "Неверный пароль."}
    else:
        return {"status": "Пользователь не найден."}
