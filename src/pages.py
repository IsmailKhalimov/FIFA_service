import io
import urllib.error
import urllib.request

import streamlit as st
from db_connection import get_filtered_clubs, get_unique_values, get_players_by_club, \
    get_trophies_by_club, get_clubs_by_trophy, get_clubs_by_country, get_clubs, get_trophies, get_country, \
    get_db_connection, get_clubs_with_ids, get_subtypes_for_categories, count_scout_players, search_scout_players, \
    count_ideal_profile_players, search_ideal_profile_players
from agg_func import players_count, trophies_count, trophywinners_count, clubsincountry_count

_IMG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


@st.cache_data(ttl=86400, show_spinner=False, max_entries=500)
def _fetch_image_bytes(url: str) -> bytes | None:
    """Загрузка по URL с User-Agent."""
    req = urllib.request.Request(url, headers=_IMG_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _player_image_candidate_urls(player_row) -> list[str]:
    """Приоритет: photo_url из БД; если пусто, на фронте рисуется локальный плейсхолдер."""
    urls: list[str] = []
    photo = player_row[5].strip() if len(player_row) > 5 and player_row[5] else ""
    if photo:
        urls.append(photo)
    return urls


def _player_image_bytes(player_row) -> bytes | None:
    for url in _player_image_candidate_urls(player_row):
        data = _fetch_image_bytes(url)
        if data:
            return data
    return None


def _render_default_player_icon() -> None:
    st.markdown(
        """
        <div style="
            width: 100%;
            aspect-ratio: 1 / 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #f3f4f6, #e5e7eb);
            border-radius: 12px;
            color: #9ca3af;
            font-size: 72px;
            font-weight: 700;
        ">👤</div>
        """,
        unsafe_allow_html=True,
    )


def render_player_cards(players):
    """Блочное отображение игроков: фото и параметры."""
    if not players:
        st.info("Нет игроков для этого клуба.")
        return
    ncols = 3
    for row_start in range(0, len(players), ncols):
        cols = st.columns(ncols)
        for col_idx, col in enumerate(cols):
            idx = row_start + col_idx
            if idx >= len(players):
                break
            p = players[idx]
            name = p[0]
            position_category = p[1]
            subtype_name = p[2]
            age = p[3]
            salary = p[4]
            nationality = p[7] if len(p) > 7 and p[7] else None
            sal = float(salary) if salary is not None else 0.0
            img_data = _player_image_bytes(p)
            with col:
                with st.container(border=True):
                    if img_data:
                        st.image(io.BytesIO(img_data), use_container_width=True)
                    else:
                        _render_default_player_icon()
                        st.caption("Фото не загружено")
                    st.markdown(f"**{name}**")
                    if nationality:
                        st.caption(
                            f"{nationality} · {position_category} · {subtype_name} · {age} лет"
                        )
                    else:
                        st.caption(
                            f"{position_category} · {subtype_name} · {age} лет"
                        )
                    st.caption(f"Зарплата: **{sal:,.0f}** $")
                    g = p[8] if len(p) > 8 else None
                    a = p[9] if len(p) > 9 else None
                    if g is not None or a is not None:
                        st.caption(
                            f"Сезон: голы **{g if g is not None else '—'}**, передачи **{a if a is not None else '—'}**"
                        )


def render_scout_player_cards(
    rows: list[tuple],
    *,
    show_fit_distance: bool = False,
) -> None:
    """Скаут: name, nationality, position_category, subtype, age, salary, photo_url, tm_id, club_name, goals, assists [, fit_dist]."""
    if not rows:
        st.info("Никого не найдено по заданным условиям.")
        return
    ncols = 3
    for row_start in range(0, len(rows), ncols):
        cols = st.columns(ncols)
        for col_idx, col in enumerate(cols):
            idx = row_start + col_idx
            if idx >= len(rows):
                break
            r = rows[idx]
            if show_fit_distance:
                name, nat, pos_c, sub_n, age, salary, photo, tm_id, club_name, g, a, fit_dist = r
            else:
                name, nat, pos_c, sub_n, age, salary, photo, tm_id, club_name, g, a = r
                fit_dist = None
            compat = (name, pos_c, sub_n, age, salary, photo, tm_id)
            sal = float(salary) if salary is not None else 0.0
            club_label = club_name if club_name else "Свободный агент"
            img_data = _player_image_bytes(compat)
            with col:
                with st.container(border=True):
                    if img_data:
                        st.image(io.BytesIO(img_data), use_container_width=True)
                    else:
                        _render_default_player_icon()
                        st.caption("Фото не загружено")
                    st.markdown(f"**{name}**")
                    st.caption(f"{nat} · {club_label}")
                    st.caption(f"{pos_c} · {sub_n} · {age} лет")
                    st.caption(f"Зарплата: **{sal:,.0f}** $")
                    st.caption(
                        f"Сезон: голы **{g if g is not None else '—'}**, передачи **{a if a is not None else '—'}**"
                    )
                    if show_fit_distance and fit_dist is not None:
                        st.caption(f"Расстояние до профиля: **{float(fit_dist):.3f}** (меньше — ближе)")


def display_player_scout() -> None:
    st.title("Скаут игрока")
    st.caption(
        "Подбор игроков по возрасту, клубу, амплуа и подклассу. "
        "Подклассы доступны после выбора амплуа. Показано по 12 карточек на страницу."
    )

    if "scout_form_key" not in st.session_state:
        st.session_state["scout_form_key"] = 0

    clubs_rows = get_clubs_with_ids()
    id_by_name = {row[1]: row[0] for row in clubs_rows}
    club_names = [row[1] for row in clubs_rows]

    categories_all = ["Вратарь", "Защитник", "Полузащитник", "Нападающий"]

    form_key = f"scout_form_{st.session_state['scout_form_key']}"
    with st.form(form_key):
        fc1, fc2 = st.columns(2)
        with fc1:
            age_min = st.number_input("Возраст от", min_value=16, max_value=55, value=16, step=1)
            age_max = st.number_input("Возраст до", min_value=16, max_value=55, value=45, step=1)
        with fc2:
            free_agents_only = st.checkbox("Только свободные агенты")
            exclude_label = st.selectbox(
                "Не показывать игроков клуба (для подбора в чужую команду)",
                ["— не исключать —"] + club_names,
            )

        sort_label = st.selectbox(
            "Сортировка",
            (
                "По умолчанию (имя)",
                "По возрасту (младшие сначала)",
                "По возрасту (старшие сначала)",
            ),
            help="По умолчанию — алфавит по имени; по возрасту — от меньшего к большему или наоборот.",
        )
        if sort_label == "По возрасту (младшие сначала)":
            sort_mode = "age"
        elif sort_label == "По возрасту (старшие сначала)":
            sort_mode = "age_desc"
        else:
            sort_mode = "default"

        selected_club_names = st.multiselect(
            "Текущий клуб (пусто = все клубы с контрактом)",
            club_names,
            disabled=free_agents_only,
            help="Если включено «Только свободные агенты», фильтр по клубам не используется.",
        )

        amp = st.multiselect("Амплуа", categories_all, help="Можно оставить пустым — тогда без фильтра по позиции.")

        subtype_labels: list[str] = []
        sub_map: dict[str, int] = {}
        if amp:
            for sid, n, cat in get_subtypes_for_categories(amp):
                label = f"{n} ({cat})"
                sub_map[label] = sid
            subtype_labels = st.multiselect(
                "Подкласс",
                sorted(sub_map.keys()),
                help="Появляется после выбора амплуа. Пусто = все подклассы в выбранных амплуа.",
            )
        else:
            st.caption("Выберите амплуа, чтобы сузить поиск по подклассу.")

        st.markdown("**Статистика за последний сезон**")
        gf1, gf2 = st.columns(2)
        with gf1:
            goals_min = st.number_input("Голы от", min_value=0, max_value=100, value=0, step=1)
            goals_max = st.number_input("Голы до", min_value=0, max_value=100, value=40, step=1)
        with gf2:
            assists_min = st.number_input("Передачи от", min_value=0, max_value=100, value=0, step=1)
            assists_max = st.number_input(
                "Передачи до", min_value=0, max_value=100, value=30, step=1
            )

        submitted = st.form_submit_button("Найти")

    if st.button("Сбросить фильтры", key="scout_btn_reset_filters"):
        st.session_state.pop("scout_filters", None)
        st.session_state.pop("scout_page", None)
        st.session_state["scout_form_key"] = st.session_state.get("scout_form_key", 0) + 1
        st.rerun()

    if submitted:
        if age_min > age_max:
            st.error("Укажите корректный диапазон возраста (от ≤ до).")
            return
        if goals_min > goals_max:
            st.error("Диапазон голов: «от» не больше «до».")
            return
        if assists_min > assists_max:
            st.error("Диапазон передач: «от» не больше «до».")
            return
        st.session_state["scout_filters"] = {
            "age_min": age_min,
            "age_max": age_max,
            "free_agents_only": free_agents_only,
            "club_ids": None
            if free_agents_only
            else ([id_by_name[n] for n in selected_club_names] if selected_club_names else None),
            "exclude_club_id": None
            if exclude_label == "— не исключать —"
            else id_by_name[exclude_label],
            "position_categories": amp if amp else None,
                    "subtype_ids": [sub_map[lb] for lb in subtype_labels] if (amp and subtype_labels) else None,
            "sort": sort_mode,
            "goals_min": goals_min,
            "goals_max": goals_max,
            "assists_min": assists_min,
            "assists_max": assists_max,
        }
        st.session_state["scout_page"] = 1

    flt = st.session_state.get("scout_filters")
    if not flt:
        st.info("Задайте условия и нажмите «Найти».")
        return

    sort_mode = flt.get("sort", "default")

    total = count_scout_players(
        age_min=flt["age_min"],
        age_max=flt["age_max"],
        free_agents_only=flt["free_agents_only"],
        club_ids=flt["club_ids"],
        exclude_club_id=flt["exclude_club_id"],
        position_categories=flt["position_categories"],
        subtype_ids=flt["subtype_ids"],
        sort_mode=sort_mode,
        goals_min=flt.get("goals_min"),
        goals_max=flt.get("goals_max"),
        assists_min=flt.get("assists_min"),
        assists_max=flt.get("assists_max"),
    )
    page_size = 12
    max_page = max(1, (total + page_size - 1) // page_size)
    page = int(st.session_state.get("scout_page", 1))
    page = max(1, min(page, max_page))
    st.session_state["scout_page"] = page

    if sort_mode == "default":
        sort_caption = "имя"
    elif sort_mode == "age_desc":
        sort_caption = "возраст ↓"
    else:
        sort_caption = "возраст ↑"
    st.subheader(
        f"Найдено: **{total}** · страница **{page}** из **{max_page}** · сортировка: **{sort_caption}**"
    )

    pc1, pc2, pc3 = st.columns([1, 1, 2])
    with pc1:
        if st.button("← Назад", disabled=page <= 1, key="scout_prev"):
            st.session_state["scout_page"] = page - 1
            st.rerun()
    with pc2:
        if st.button("Вперёд →", disabled=page >= max_page, key="scout_next"):
            st.session_state["scout_page"] = page + 1
            st.rerun()

    offset = (page - 1) * page_size
    rows = search_scout_players(
        age_min=flt["age_min"],
        age_max=flt["age_max"],
        free_agents_only=flt["free_agents_only"],
        club_ids=flt["club_ids"],
        exclude_club_id=flt["exclude_club_id"],
        position_categories=flt["position_categories"],
        subtype_ids=flt["subtype_ids"],
        limit=page_size,
        offset=offset,
        sort_mode=sort_mode,
        goals_min=flt.get("goals_min"),
        goals_max=flt.get("goals_max"),
        assists_min=flt.get("assists_min"),
        assists_max=flt.get("assists_max"),
    )
    render_scout_player_cards(rows)


def display_ideal_recommendations() -> None:
    """Вариант B: ранжирование по взвешенному расстоянию до целевого профиля (голы и передачи за сезон учитываются)."""
    st.title("Рекомендации по профилю")
    st.caption(
        "Сначала сужаете выборку (как в скауте), затем задаёте «идеальную точку»: возраст, зарплату, голы и передачи за последний сезон. "
        "Веса масштабируют вклад признаков. Расстояние нормализовано (возраст ~40 лет, зарплата ~50 млн $, голы ~30, передачи ~25)."
    )

    if "ideal_form_key" not in st.session_state:
        st.session_state["ideal_form_key"] = 0

    clubs_rows = get_clubs_with_ids()
    id_by_name = {row[1]: row[0] for row in clubs_rows}
    club_names = [row[1] for row in clubs_rows]
    categories_all = ["Вратарь", "Защитник", "Полузащитник", "Нападающий"]

    form_key = f"ideal_form_{st.session_state['ideal_form_key']}"
    with st.form(form_key):
        fc1, fc2 = st.columns(2)
        with fc1:
            age_min = st.number_input("Возраст от", min_value=16, max_value=55, value=16, step=1, key="ideal_age_min")
            age_max = st.number_input("Возраст до", min_value=16, max_value=55, value=45, step=1, key="ideal_age_max")
        with fc2:
            free_agents_only = st.checkbox("Только свободные агенты", key="ideal_fa")
            exclude_label = st.selectbox(
                "Не показывать игроков клуба",
                ["— не исключать —"] + club_names,
                key="ideal_excl",
            )

        selected_club_names = st.multiselect(
            "Текущий клуб (пусто = все с контрактом)",
            club_names,
            disabled=free_agents_only,
            key="ideal_clubs",
        )
        amp = st.multiselect("Амплуа", categories_all, key="ideal_amp")

        subtype_labels: list[str] = []
        sub_map: dict[str, int] = {}
        if amp:
            for sid, n, cat in get_subtypes_for_categories(amp):
                label = f"{n} ({cat})"
                sub_map[label] = sid
            subtype_labels = st.multiselect("Подкласс", sorted(sub_map.keys()), key="ideal_sub")

        st.markdown("**Статистика за последний сезон (сужение выборки)**")
        ig1, ig2 = st.columns(2)
        with ig1:
            goals_min = st.number_input("Голы от", 0, 100, 0, key="ideal_gmin")
            goals_max = st.number_input("Голы до", 0, 100, 40, key="ideal_gmax")
        with ig2:
            assists_min = st.number_input("Передачи от", 0, 100, 0, key="ideal_amin")
            assists_max = st.number_input("Передачи до", 0, 100, 30, key="ideal_amax")

        st.markdown("**Целевой профиль (идеальная точка)**")
        t1, t2 = st.columns(2)
        with t1:
            target_age = st.number_input("Целевой возраст", 16, 55, 26, step=1)
            target_salary = st.number_input("Целевая зарплата ($)", min_value=0, value=8_000_000, step=100_000)
        with t2:
            target_goals = st.number_input("Целевые голы за сезон", 0, 60, 12, step=1)
            target_assists = st.number_input("Целевые передачи за сезон", 0, 60, 8, step=1)

        st.markdown("**Веса признаков** (0 = не учитывать)")
        w1, w2, w3, w4 = st.columns(4)
        with w1:
            w_age = st.slider("Возраст", 0.0, 3.0, 1.0, 0.1)
        with w2:
            w_salary = st.slider("Зарплата", 0.0, 3.0, 1.0, 0.1)
        with w3:
            w_goals = st.slider("Голы", 0.0, 3.0, 1.2, 0.1)
        with w4:
            w_assists = st.slider("Передачи", 0.0, 3.0, 1.0, 0.1)

        submitted = st.form_submit_button("Подобрать")

    if st.button("Сбросить фильтры", key="ideal_btn_reset"):
        st.session_state.pop("ideal_filters", None)
        st.session_state.pop("ideal_page", None)
        st.session_state["ideal_form_key"] = st.session_state.get("ideal_form_key", 0) + 1
        st.rerun()

    if submitted:
        if age_min > age_max:
            st.error("Укажите корректный диапазон возраста (от ≤ до).")
            return
        if goals_min > goals_max:
            st.error("Диапазон голов: «от» не больше «до».")
            return
        if assists_min > assists_max:
            st.error("Диапазон передач: «от» не больше «до».")
            return
        st.session_state["ideal_filters"] = {
            "age_min": age_min,
            "age_max": age_max,
            "free_agents_only": free_agents_only,
            "club_ids": None
            if free_agents_only
            else ([id_by_name[n] for n in selected_club_names] if selected_club_names else None),
            "exclude_club_id": None if exclude_label == "— не исключать —" else id_by_name[exclude_label],
            "position_categories": amp if amp else None,
            "subtype_ids": [sub_map[lb] for lb in subtype_labels] if (amp and subtype_labels) else None,
            "goals_min": goals_min,
            "goals_max": goals_max,
            "assists_min": assists_min,
            "assists_max": assists_max,
            "target_age": float(target_age),
            "target_salary": float(target_salary),
            "target_goals": float(target_goals),
            "target_assists": float(target_assists),
            "weight_age": float(w_age),
            "weight_salary": float(w_salary),
            "weight_goals": float(w_goals),
            "weight_assists": float(w_assists),
        }
        st.session_state["ideal_page"] = 1

    flt = st.session_state.get("ideal_filters")
    if not flt:
        st.info("Задайте условия и нажмите «Подобрать».")
        return

    total = count_ideal_profile_players(
        age_min=flt["age_min"],
        age_max=flt["age_max"],
        free_agents_only=flt["free_agents_only"],
        club_ids=flt["club_ids"],
        exclude_club_id=flt["exclude_club_id"],
        position_categories=flt["position_categories"],
        subtype_ids=flt["subtype_ids"],
        goals_min=flt.get("goals_min"),
        goals_max=flt.get("goals_max"),
        assists_min=flt.get("assists_min"),
        assists_max=flt.get("assists_max"),
    )
    page_size = 12
    max_page = max(1, (total + page_size - 1) // page_size)
    page = int(st.session_state.get("ideal_page", 1))
    page = max(1, min(page, max_page))
    st.session_state["ideal_page"] = page

    st.subheader(f"Найдено: **{total}** · страница **{page}** из **{max_page}** · сортировка: **близость к профилю**")

    pc1, pc2, pc3 = st.columns([1, 1, 2])
    with pc1:
        if st.button("← Назад", disabled=page <= 1, key="ideal_prev"):
            st.session_state["ideal_page"] = page - 1
            st.rerun()
    with pc2:
        if st.button("Вперёд →", disabled=page >= max_page, key="ideal_next"):
            st.session_state["ideal_page"] = page + 1
            st.rerun()

    offset = (page - 1) * page_size
    rows = search_ideal_profile_players(
        age_min=flt["age_min"],
        age_max=flt["age_max"],
        free_agents_only=flt["free_agents_only"],
        club_ids=flt["club_ids"],
        exclude_club_id=flt["exclude_club_id"],
        position_categories=flt["position_categories"],
        subtype_ids=flt["subtype_ids"],
        goals_min=flt.get("goals_min"),
        goals_max=flt.get("goals_max"),
        assists_min=flt.get("assists_min"),
        assists_max=flt.get("assists_max"),
        target_age=flt["target_age"],
        target_salary=flt["target_salary"],
        target_goals=flt["target_goals"],
        target_assists=flt["target_assists"],
        weight_age=flt["weight_age"],
        weight_salary=flt["weight_salary"],
        weight_goals=flt["weight_goals"],
        weight_assists=flt["weight_assists"],
        limit=page_size,
        offset=offset,
    )
    render_scout_player_cards(rows, show_fit_distance=True)


def logout():
    st.session_state["logged_in"] = False
    st.session_state["username"] = None


def main_page(role):
    st.sidebar.title(f"Добро пожаловать, {st.session_state['username']}!")
    st.sidebar.button("Выйти", on_click=logout)
    if role == 'user':
        page = st.sidebar.radio(
            "Выберите страницу",
            ("Фильтрация клубов", "Список игроков", "Скаут игрока", "Рекомендации по профилю"),
        )

        if page == "Фильтрация клубов":
            display_club_filtering()
        elif page == "Список игроков":
            display_additional_info()
        elif page == "Скаут игрока":
            display_player_scout()
        elif page == "Рекомендации по профилю":
            display_ideal_recommendations()
    elif role == "reporter":
        page = st.sidebar.radio(
            "Выберите страницу",
            (
                "Фильтрация клубов",
                "Список игроков",
                "Скаут игрока",
                "Рекомендации по профилю",
                "Добавить трофей клубу",
            ),
        )

        if page == "Фильтрация клубов":
            display_club_filtering()
        elif page == "Список игроков":
            display_additional_info()
        elif page == "Скаут игрока":
            display_player_scout()
        elif page == "Рекомендации по профилю":
            display_ideal_recommendations()
        elif page == "Добавить трофей клубу":
            add_trophy_to_club()
    elif role == 'admin':
        page = st.sidebar.radio(
            "Выберите страницу",
            (
                "Фильтрация клубов",
                "Список игроков",
                "Скаут игрока",
                "Рекомендации по профилю",
                "Добавить трофей клубу",
                "Оформить трансфер игрока в другой клуб",
            ),
        )

        if page == "Фильтрация клубов":
            display_club_filtering()
        elif page == "Список игроков":
            display_additional_info()
        elif page == "Скаут игрока":
            display_player_scout()
        elif page == "Рекомендации по профилю":
            display_ideal_recommendations()
        elif page == "Добавить трофей клубу":
            add_trophy_to_club()
        elif page == "Оформить трансфер игрока в другой клуб":
            transfer_player()


def transfer_player():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT club_id, name FROM Club ORDER BY name;")
    clubs = cursor.fetchall()
    club_dict = {club[1]: club[0] for club in clubs}

    st.header("Оформить трансфер игрока в другой клуб")

    or_club_name = st.selectbox("Выберите клуб, в котором игрок сейчас играет", options=list(club_dict.keys()))
    cursor.execute(
        """
        SELECT player_id, name 
        FROM Player
        WHERE club_id = %s
        ORDER BY name;
        """, (club_dict[or_club_name],))
    players = cursor.fetchall()
    player_dict = {player[1]: player[0] for player in players}

    conn.close()

    player_name = st.selectbox("Выберите игрока", options=list(player_dict.keys()))
    salary = st.number_input("Введите новую зарплату", min_value=0, max_value=999999999, step=10000, value=100000)
    tr_club_name = st.selectbox("Выберите клуб, в который игрок перейдёт", options=list(club_dict.keys()))

    if st.button("Оформить трансфер игрока"):
        if or_club_name == tr_club_name:
            st.error('Игрок не может перейти в клуб, в котором уже играет')
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE Player 
                SET club_id = %s, salary = %s
                WHERE player_id = %s
                """,
                (club_dict[tr_club_name], salary, player_dict[player_name])
            )
            conn.commit()
            st.success(f"Игрок \"{player_name}\" добавлен в клуб \"{tr_club_name}\" с зарплатой {salary}$ в год.")
        except Exception as e:
            conn.rollback()
            st.error(f"Ошибка: {e}")
        finally:
            conn.close()


def add_trophy_to_club():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT club_id, name FROM Club ORDER BY name;")
    clubs = cursor.fetchall()
    club_dict = {club[1]: club[0] for club in clubs}

    cursor.execute("SELECT trophy_id, name FROM Trophy ORDER BY name;")
    trophies = cursor.fetchall()
    trophy_dict = {trophy[1]: trophy[0] for trophy in trophies}

    conn.close()

    st.header("Добавить трофей клубу")

    club_name = st.selectbox("Выберите клуб", options=list(club_dict.keys()))
    trophy_name = st.selectbox("Выберите трофей", options=list(trophy_dict.keys()))
    year_won = st.number_input("Введите год получения трофея", min_value=1800, max_value=2100, step=1, value=2023)

    if st.button("Добавить трофей"):
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO Club_Trophy (club_id, trophy_id, year_won)
                VALUES (%s, %s, %s);
                """,
                (club_dict[club_name], trophy_dict[trophy_name], year_won)
            )
            conn.commit()
            st.success(f"Трофей \"{trophy_name}\" добавлен клубу \"{club_name}\" за {year_won} год.")
        except Exception as e:
            conn.rollback()
            st.error(f"Ошибка: {e}")
        finally:
            conn.close()


def display_club_filtering():
    cities, stadiums = get_unique_values()
    st.sidebar.header("Фильтры")
    filters = {}

    min_rating = st.sidebar.slider("Минимальный рейтинг клуба", 0, 100, 0)
    if min_rating > 0:
        filters["rating"] = min_rating

    city_filter = st.sidebar.selectbox("Город", ["Все"] + cities)
    if city_filter != "Все":
        filters["city"] = city_filter

    stadium_filter = st.sidebar.selectbox("Стадион", ["Все"] + stadiums)
    if stadium_filter != "Все":
        filters["stadium"] = stadium_filter

    if st.sidebar.button("Применить фильтры"):
        st.write("Результаты фильтрации:")
        clubs = get_filtered_clubs(filters)
        if clubs:
            st.table([{"Название клуба": club[0], "Стадион": club[1], "Город": club[2], "Рейтинг": club[3],
                       "Кол-во игроков": club[4]} for club in
                      clubs])
        else:
            st.write("Нет данных, соответствующих фильтрам.")


def display_additional_info():
    st.title("Список игроков клуба")
    st.sidebar.header("Выберите тип информации")
    query_type = st.sidebar.selectbox(
        "Что вы хотите узнать?",
        ["Список игроков клуба", "Список трофеев клуба", "Клубы, выигравшие трофей", "Клубы из страны"]
    )

    if query_type == "Список игроков клуба":
        club_name = st.selectbox("Выберете клуб из списка", get_clubs())
        if club_name:
            players = get_players_by_club(club_name)
            if st.button("Показать карточки игроков"):
                render_player_cards(players)
                st.subheader("Сводка по клубу")
                st.table(
                    [{"Название клуба": club[0], "Рейтинг клуба": club[1], "Количество игроков": club[2]}
                     for club in players_count(club_name)]
                )

    elif query_type == "Список трофеев клуба":
        club_name = st.selectbox("Выберете клуб из списка", get_clubs())
        if club_name:
            trophies = get_trophies_by_club(club_name)
            if st.button('Показать список'):
                st.table(
                    [{'Название трофея': trophy[0], 'Год получения': trophy[1], 'Призовой фонд': trophy[2]} for trophy
                     in trophies] if trophies else [{"Сообщение": "Клуб не выиграл трофеев"}])
                st.caption(f"Количество трофеев у клуба {club_name}: {trophies_count(club_name)}")

    elif query_type == "Клубы, выигравшие трофей":
        trophy_name = st.selectbox("Выберете трофей из списка", get_trophies())
        if trophy_name:
            clubs = get_clubs_by_trophy(trophy_name)
            if st.button('Показать список'):
                st.table([{'Название клуба': club[0], 'Год получения': club[1]} for club in clubs] if clubs else [
                    {"Сообщение": "Нет клубов, выигравших этот трофей"}])
                st.caption(f"Количество клубов выигравших {trophy_name}: {trophywinners_count(trophy_name)}")

    elif query_type == "Клубы из страны":
        country_name = st.selectbox("Выберете страну из списка", get_country())
        if country_name:
            clubs = get_clubs_by_country(country_name)
            if st.button('Показать список'):
                st.table([{'Название клуба': club[0], 'Город': club[1]} for club in clubs] if clubs else [
                    {"Сообщение": "Нет клубов из этой страны"}])
                st.caption(f"Количество клубов, находящихся в стране {country_name}: {clubsincountry_count(country_name)}")
