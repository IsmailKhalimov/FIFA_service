from __future__ import annotations

import streamlit as st

from tm_images import fetch_player_portrait_url as _fetch_player_portrait_url_core


@st.cache_data(ttl=604800, max_entries=400, show_spinner=False)
def get_player_portrait_url(player_name: str) -> str | None:
    url, _source = _fetch_player_portrait_url_core(player_name)
    return url
