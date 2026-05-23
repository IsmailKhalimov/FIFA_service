import psycopg2
from db_connection import get_db_connection


def players_count(club_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.name, c.rating, COUNT(p.player_id)
        FROM player p JOIN club c USING(club_id)
        GROUP BY 1, 2
        HAVING c.name = %s
        """, (club_name,))
    count = cursor.fetchall()
    return count


def trophies_count(club_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(c_t.trophy_id)
        FROM club_trophy c_t JOIN club c USING (club_id)
        WHERE c.name = %s
        """, (club_name,))
    count = cursor.fetchall()
    return count[0][0]


def trophywinners_count(trophy_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(c_t.club_id)
        FROM club_trophy c_t JOIN trophy t USING (trophy_id)
        WHERE t.name = %s
        """, (trophy_name,))
    count = cursor.fetchall()
    return count[0][0]


def clubsincountry_count(country_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(c.club_id)
        FROM club c 
             JOIN stadium USING(stadium_id)
             JOIN city ci USING(city_id)
             JOIN country co USING(country_id)
        WHERE co.name = %s
        """, (country_name,))
    count = cursor.fetchall()
    return count[0][0]
