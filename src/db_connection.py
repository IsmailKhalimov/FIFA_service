import os

import psycopg2

from config import get_database_settings


def get_db_connection():
    os.environ.setdefault("PGCLIENTENCODING", "UTF8")
    s = get_database_settings()
    connect_kw = {
        "dbname": s["dbname"],
        "user": s["user"],
        "password": s["password"],
        "host": s["host"],
        "port": s["port"],
    }
    if s.get("sslmode"):
        connect_kw["sslmode"] = s["sslmode"]
    conn = psycopg2.connect(**connect_kw)
    conn.set_client_encoding("UTF8")
    return conn


def get_country():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT name
        FROM country
        ORDER BY 1;
        """
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    return [country[0] for country in results]


def get_trophies():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT name
        FROM trophy
        ORDER BY 1;
        """
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    return [trophy[0] for trophy in results]

def get_clubs():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT name
    FROM Club
    ORDER BY 1;
    """
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    return [club[0] for club in results]


def get_clubs_with_ids():
    """Список клубов (club_id, name) для фильтров скаута."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT club_id, name FROM Club ORDER BY name;")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_subtypes_for_categories(position_categories: list[str]) -> list[tuple[int, str, str]]:
    """Подклассы для выбранных амплуа: (subtype_id, name, position_category)."""
    if not position_categories:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT subtype_id, name, position_category
        FROM player_subtype
        WHERE position_category = ANY(%s)
        ORDER BY position_category, name;
        """,
        (position_categories,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def _scout_base_from_where(
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    goals_min: int | None,
    goals_max: int | None,
    assists_min: int | None,
    assists_max: int | None,
) -> tuple[str, list]:
    """Общий FROM/WHERE для скаута и рекомендаций по профилю."""
    params: list = []
    from_clause = """
        FROM Player p
        JOIN player_subtype ps ON p.subtype_id = ps.subtype_id
        JOIN Country cn ON p.nationality_country_id = cn.country_id
        LEFT JOIN Club c ON p.club_id = c.club_id
        WHERE p.age BETWEEN %s AND %s
    """
    params.extend([age_min, age_max])

    if free_agents_only:
        from_clause += " AND p.club_id IS NULL"
    else:
        if club_ids:
            from_clause += " AND p.club_id = ANY(%s)"
            params.append(club_ids)
        else:
            from_clause += " AND p.club_id IS NOT NULL"

    if exclude_club_id is not None:
        from_clause += " AND (p.club_id IS NULL OR p.club_id <> %s)"
        params.append(exclude_club_id)

    if subtype_ids:
        from_clause += " AND p.subtype_id = ANY(%s)"
        params.append(subtype_ids)
    elif position_categories:
        from_clause += " AND ps.position_category = ANY(%s)"
        params.append(position_categories)

    if goals_min is not None:
        from_clause += " AND p.goals_last_season >= %s"
        params.append(goals_min)
    if goals_max is not None:
        from_clause += " AND p.goals_last_season <= %s"
        params.append(goals_max)
    if assists_min is not None:
        from_clause += " AND p.assists_last_season >= %s"
        params.append(assists_min)
    if assists_max is not None:
        from_clause += " AND p.assists_last_season <= %s"
        params.append(assists_max)

    return from_clause, params


def count_scout_players(
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    sort_mode: str = "default",
    goals_min: int | None = None,
    goals_max: int | None = None,
    assists_min: int | None = None,
    assists_max: int | None = None,
) -> int:
    """Число игроков по критериям скаута (для пагинации)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    q, params = _scout_player_sql(
        select_count=True,
        age_min=age_min,
        age_max=age_max,
        free_agents_only=free_agents_only,
        club_ids=club_ids,
        exclude_club_id=exclude_club_id,
        position_categories=position_categories,
        subtype_ids=subtype_ids,
        sort_mode=sort_mode,
        goals_min=goals_min,
        goals_max=goals_max,
        assists_min=assists_min,
        assists_max=assists_max,
    )
    cursor.execute(q, params)
    n = cursor.fetchone()[0]
    conn.close()
    return int(n)


def search_scout_players(
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    limit: int,
    offset: int,
    sort_mode: str = "default",
    goals_min: int | None = None,
    goals_max: int | None = None,
    assists_min: int | None = None,
    assists_max: int | None = None,
) -> list[tuple]:
    """Карточки скаута: name, nationality, position_category, subtype, age, salary, photo_url, tm_id, club_name, goals, assists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    q, params = _scout_player_sql(
        select_count=False,
        age_min=age_min,
        age_max=age_max,
        free_agents_only=free_agents_only,
        club_ids=club_ids,
        exclude_club_id=exclude_club_id,
        position_categories=position_categories,
        subtype_ids=subtype_ids,
        limit=limit,
        offset=offset,
        sort_mode=sort_mode,
        goals_min=goals_min,
        goals_max=goals_max,
        assists_min=assists_min,
        assists_max=assists_max,
    )
    cursor.execute(q, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def _scout_player_sql(
    *,
    select_count: bool,
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    limit: int = 10,
    offset: int = 0,
    sort_mode: str = "default",
    goals_min: int | None = None,
    goals_max: int | None = None,
    assists_min: int | None = None,
    assists_max: int | None = None,
) -> tuple[str, list]:
    from_clause, params = _scout_base_from_where(
        age_min=age_min,
        age_max=age_max,
        free_agents_only=free_agents_only,
        club_ids=club_ids,
        exclude_club_id=exclude_club_id,
        position_categories=position_categories,
        subtype_ids=subtype_ids,
        goals_min=goals_min,
        goals_max=goals_max,
        assists_min=assists_min,
        assists_max=assists_max,
    )
    if select_count:
        sel = "SELECT COUNT(*)"
    else:
        sel = """
        SELECT p.name, cn.name, ps.position_category, ps.name, p.age, p.salary,
               p.photo_url, p.transfermarkt_player_id, c.name,
               p.goals_last_season, p.assists_last_season
        """

    if select_count:
        order = ""
    elif sort_mode == "age":
        order = " ORDER BY p.age ASC, p.name, p.player_id"
    elif sort_mode == "age_desc":
        order = " ORDER BY p.age DESC, p.name, p.player_id"
    else:
        order = " ORDER BY p.name, p.player_id"
    lim = "" if select_count else " LIMIT %s OFFSET %s"
    if not select_count:
        params.extend([limit, offset])

    return sel + from_clause + order + lim, params


def count_ideal_profile_players(
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    goals_min: int | None = None,
    goals_max: int | None = None,
    assists_min: int | None = None,
    assists_max: int | None = None,
) -> int:
    """Число кандидатов для рекомендаций (вариант B: та же выборка, что у скаута)."""
    from_clause, params = _scout_base_from_where(
        age_min=age_min,
        age_max=age_max,
        free_agents_only=free_agents_only,
        club_ids=club_ids,
        exclude_club_id=exclude_club_id,
        position_categories=position_categories,
        subtype_ids=subtype_ids,
        goals_min=goals_min,
        goals_max=goals_max,
        assists_min=assists_min,
        assists_max=assists_max,
    )
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*)" + from_clause, params)
    n = cursor.fetchone()[0]
    conn.close()
    return int(n)


def search_ideal_profile_players(
    age_min: int,
    age_max: int,
    free_agents_only: bool,
    club_ids: list[int] | None,
    exclude_club_id: int | None,
    position_categories: list[str] | None,
    subtype_ids: list[int] | None,
    goals_min: int | None,
    goals_max: int | None,
    assists_min: int | None,
    assists_max: int | None,
    target_age: float,
    target_salary: float,
    target_goals: float,
    target_assists: float,
    weight_age: float,
    weight_salary: float,
    weight_goals: float,
    weight_assists: float,
    limit: int,
    offset: int,
) -> list[tuple]:
    """
    Вариант B: сортировка по взвешенному расстоянию до целевого профиля (нормализация по шкалам).
    Строка: как у скаута + goals, assists + fit_dist (меньше — ближе к цели).
    """
    from_clause, base_params = _scout_base_from_where(
        age_min=age_min,
        age_max=age_max,
        free_agents_only=free_agents_only,
        club_ids=club_ids,
        exclude_club_id=exclude_club_id,
        position_categories=position_categories,
        subtype_ids=subtype_ids,
        goals_min=goals_min,
        goals_max=goals_max,
        assists_min=assists_min,
        assists_max=assists_max,
    )
    inner_select = """
        SELECT p.name, cn.name, ps.position_category, ps.name, p.age, p.salary,
               p.photo_url, p.transfermarkt_player_id, c.name,
               p.goals_last_season, p.assists_last_season,
               (
                 %s * ABS(p.age - %s)::numeric / 40.0 +
                 %s * ABS(p.salary - %s) / 50000000.0 +
                 %s * ABS(COALESCE(p.goals_last_season, 0) - %s)::numeric / 30.0 +
                 %s * ABS(COALESCE(p.assists_last_season, 0) - %s)::numeric / 25.0
               ) AS fit_dist
    """
    dist_params = [
        weight_age,
        target_age,
        weight_salary,
        target_salary,
        weight_goals,
        target_goals,
        weight_assists,
        target_assists,
    ]
    q = (
        inner_select
        + from_clause
        + " ORDER BY fit_dist ASC, p.name, p.player_id LIMIT %s OFFSET %s"
    )
    params = dist_params + base_params + [limit, offset]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(q, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


# Функция для получения уникальных значений для фильтров
def get_unique_values():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT ci.name FROM City ci ORDER BY ci.name;")
    cities = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT s.name FROM Stadium s ORDER BY s.name;")
    stadiums = [row[0] for row in cursor.fetchall()]

    conn.close()
    return cities, stadiums


# Функция для получения клубов с фильтрацией
def get_filtered_clubs(filters):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT c.name, s.name AS stadium, ci.name AS city, c.rating, COUNT(player_id)
    FROM Club c
    JOIN Stadium s ON c.stadium_id = s.stadium_id
    JOIN City ci ON s.city_id = ci.city_id
    JOIN Player p ON c.club_id = p.club_id
    WHERE 1=1
    """

    params = []

    # Передача условий фильтрации из словаря
    if "rating" in filters:
        query += " AND c.rating >= %s"
        params.append(filters["rating"])

    if "city" in filters:
        query += " AND ci.name = %s"
        params.append(filters["city"])

    if "stadium" in filters:
        query += " AND s.name = %s"
        params.append(filters["stadium"])

    query += "\nGROUP BY 1, 2, 3, 4 ORDER BY c.rating DESC;"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


# Получение игроков клуба
def get_players_by_club(club_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT p.name, ps.position_category, ps.name, p.age, p.salary,
           p.photo_url, p.transfermarkt_player_id, cn.name,
           p.goals_last_season, p.assists_last_season
    FROM Player p
    JOIN Club c ON p.club_id = c.club_id
    JOIN player_subtype ps ON p.subtype_id = ps.subtype_id
    JOIN Country cn ON p.nationality_country_id = cn.country_id
    WHERE c.name = %s
    ORDER BY 1;
    """
    cursor.execute(query, (club_name,))
    players = cursor.fetchall()
    conn.close()
    return players


# Получение трофеев, выигранных клубом
def get_trophies_by_club(club_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT t.name, ct.year_won, t.prize_fund
    FROM Club_Trophy ct
    JOIN Trophy t ON ct.trophy_id = t.trophy_id
    JOIN Club c ON ct.club_id = c.club_id
    WHERE c.name = %s
    ORDER BY 2;
    """
    cursor.execute(query, (club_name,))
    trophies = cursor.fetchall()
    conn.close()
    return trophies

# Получение клубов, выигравших определенный трофей
def get_clubs_by_trophy(trophy_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT c.name, ct.year_won
    FROM Club_Trophy ct
    JOIN Trophy t ON ct.trophy_id = t.trophy_id
    JOIN Club c ON ct.club_id = c.club_id
    WHERE t.name = %s
    ORDER BY 2;
    """
    cursor.execute(query, (trophy_name,))
    clubs = cursor.fetchall()
    conn.close()
    return clubs

# Получение клубов из определенной страны
def get_clubs_by_country(country_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT c.name, ci.name
    FROM Club c
    JOIN Stadium s ON c.stadium_id = s.stadium_id
    JOIN City ci ON s.city_id = ci.city_id
    JOIN Country co ON ci.country_id = co.country_id
    WHERE co.name = %s
    ORDER BY 1;
    """
    cursor.execute(query, (country_name,))
    clubs = cursor.fetchall()
    conn.close()
    return clubs

