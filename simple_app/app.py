import streamlit as st
import pandas as pd

from analysis.math_logic import (
    parse_values,
    calculate_mean,
    calculate_min,
    calculate_max,
    normalize,
    estimate_slope,
)

from analysis.db import (
    init_db,
    insert_result,
    fetch_results,
)

# ======================================================
# Alap beállítások
# ======================================================
st.set_page_config(page_title="Görbe elemző app", layout="centered")
st.title("Görbe elemző alkalmazás")

# ======================================================
# Adatbázis inicializálás
# ======================================================
init_db()

# ======================================================
# Session state inicializálás
# ======================================================
if "data" not in st.session_state:
    st.session_state["data"] = None

if "show_normalized" not in st.session_state:
    st.session_state["show_normalized"] = True

if "last_raw_input" not in st.session_state:
    st.session_state["last_raw_input"] = ""

# ======================================================
# Oldalak (tabek)
# ======================================================
tab_input, tab_output, tab_history = st.tabs(
    ["🔢 Input adatok", "📊 Eredmények", "🗄️ Korábbi futások"]
)

# ======================================================
# INPUT OLDAL
# ======================================================
with tab_input:
    st.header("Bemeneti adatok")

    raw_input = st.text_input(
        "Adj meg számokat vesszővel elválasztva",
        value="1,2,3,4,5"
    )

    st.session_state["show_normalized"] = st.checkbox(
        "Normalizált görbe számítása",
        value=st.session_state["show_normalized"]
    )

    if st.button("Elemzés futtatása"):
        try:
            parsed = parse_values(raw_input)

            if len(parsed) < 2:
                st.error("Legalább 2 értéket adj meg.")
            else:
                # ---- Session state frissítés ----
                st.session_state["data"] = parsed
                st.session_state["last_raw_input"] = raw_input

                # ---- Számítások ----
                mean_val = calculate_mean(parsed)
                min_val = calculate_min(parsed)
                max_val = calculate_max(parsed)
                slope_val = estimate_slope(parsed)

                # ---- Mentés adatbázisba ----
                insert_result(
                    raw_data=raw_input,
                    mean=mean_val,
                    min_val=min_val,
                    max_val=max_val,
                    slope=slope_val
                )

                st.success("Elemzés lefutott és mentésre került ✔️")

        except ValueError:
            st.error("Hibás bemenet! Csak számokat adj meg.")

# ======================================================
# OUTPUT OLDAL
# ======================================================
with tab_output:
    st.header("Eredmények")

    if st.session_state["data"] is None:
        st.info("Először add meg az input adatokat az Input oldalon.")
        st.stop()

    values = st.session_state["data"]

    df = pd.DataFrame({
        "index": range(len(values)),
        "raw": values
    }).set_index("index")

    if st.session_state["show_normalized"]:
        df["normalized"] = normalize(values)

    st.line_chart(df)

    st.subheader("Statisztikák")
    st.write(f"Átlag: {calculate_mean(values):.2f}")
    st.write(f"Minimum: {calculate_min(values):.2f}")
    st.write(f"Maximum: {calculate_max(values):.2f}")
    st.write(f"Meredekség: {estimate_slope(values):.2f}")

# ======================================================
# KORÁBBI FUTÁSOK
# ======================================================
with tab_history:
    st.header("Korábbi elemzések")

    rows = fetch_results()

    if not rows:
        st.info("Még nincs mentett elemzés.")
    else:
        df_history = pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Raw input",
                "Átlag",
                "Minimum",
                "Maximum",
                "Meredekség",
                "Időpont"
            ]
        )

        st.dataframe(df_history, use_container_width=True)




