import streamlit as st
import pandas as pd

st.set_page_config(page_title="PCR app", layout="wide")

st.sidebar.header("Menü")

input_view = None
result_view = None

with st.sidebar.expander("Bemeneti adatok", expanded=False):
    input_view = st.radio(
        "",
        ["Futási file", "Targetek", "Minta azonosítók"],
        index=None,
        key="input"
    )

with st.sidebar.expander("Eredmények", expanded=False):
    result_view = st.radio(
        "",
        ["Táblázatos megjelenítés", "PCR görbe megjelenítés"],
        index=None,
        key="results"
    )

# ===== KÖZÖS KIVÁLASZTÁS =====
selected_view = input_view or result_view

# ===== FŐOLDAL =====
if selected_view is None:
    st.title("Webalapú PCR alkalmazás")
    st.write("Válassz funkciót a bal oldali menüből.")

# ===== BEMENETI ADATOK =====
elif selected_view == "Futási file":
    st.title("Futási file")
    uploaded_file = st.file_uploader("Válaszd ki a futási fájlt")
    if uploaded_file:
        st.success(f"Fájl feltöltve: {uploaded_file.name}")


elif selected_view == "Targetek":
    st.title("Targetek")
    st.write("Állítsd be a festékek szerepét és adj meg vizsgált target nevet, ha szükséges.")
    dyes = ["FAM", "VIC", "ABY", "Cy5", "ROX"]
    roles = ["Referencia festék", "Internal Kontroll", "Vizsgált target"]

    # Prefill session_state from existing saved DataFrame (if any)
    if "dye_targets_df" in st.session_state:
        df_existing = st.session_state["dye_targets_df"]
        for _, row in df_existing.iterrows():
            dye = row["dye"]
            val = row["Target"]
            if val in roles:
                st.session_state.setdefault(f"{dye}_role", val)
                st.session_state.setdefault(f"{dye}_target", "")
            else:
                st.session_state.setdefault(f"{dye}_role", "Vizsgált target")
                st.session_state.setdefault(f"{dye}_target", val)
    else:
        for dye in dyes:
            st.session_state.setdefault(f"{dye}_role", roles[0])
            st.session_state.setdefault(f"{dye}_target", "")

    # Render role selection as radios (one row per dye)
    for dye in dyes:
        st.subheader(dye)
        # current value (prefilled into the radio via session_state key)
        current_role = st.session_state.get(f"{dye}_role", roles[0])
        role = st.radio(
            "Válassz szerepet:",
            roles,
            index=roles.index(current_role) if current_role in roles else 0,
            key=f"{dye}_role",
        )

        st.write("Kijelölt szerep:", role)

        # If the role is 'Vizsgálat', allow free-text target name (editable)
        if role == "Vizsgált target":
            st.session_state[f"{dye}_target"] = st.text_input(
                f"{dye} vizsgált target neve",
                value=st.session_state.get(f"{dye}_target", ""),
                key=f"{dye}_target_input",
            )

        # visual separator between dye blocks (skip after last)
        if dye != dyes[-1]:
            st.markdown("---")

    # Save and reset controls
    col_save, col_reset = st.columns([1, 1])
    if col_save.button("Mentés"):
        records = []
        for dye in dyes:
            role = st.session_state.get(f"{dye}_role", roles[0])
            if role == "Vizsgált target":
                target_value = st.session_state.get(f"{dye}_target", "")
            else:
                target_value = role
            records.append({"dye": dye, "Target": target_value})
        df = pd.DataFrame(records)
        st.session_state["dye_targets_df"] = df
        # Also store under an explicit variable name for downstream evaluation
        st.session_state["dye_targets_var"] = df
        # expose as module-global for immediate use in this run
        globals()["dye_targets_df"] = df
        st.success("Festékek és targetek elmentve.")

    if col_reset.button("Reset beállítások"):
        for dye in dyes:
            st.session_state[f"{dye}_role"] = roles[0]
            st.session_state[f"{dye}_target"] = ""
        if "dye_targets_df" in st.session_state:
            del st.session_state["dye_targets_df"]
        if "dye_targets_var" in st.session_state:
            del st.session_state["dye_targets_var"]
        if "dye_targets_df" in globals():
            del globals()["dye_targets_df"]
        st.experimental_rerun()

    # Display saved table if present
    if "dye_targets_df" in st.session_state:
        st.write("Mentett beállítások:")
        df = st.session_state["dye_targets_df"]
        # Render a compact HTML table so columns don't expand to full page width
        css = """
        <style>
        .compact-table table {border-collapse: collapse; display: inline-block;}
        .compact-table th, .compact-table td {padding:6px 10px; white-space:nowrap; text-align:left; border:1px solid #ddd;}
        .compact-table th {background: #ffffff; color: #6b6b6b; font-weight: 600;}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(df.to_html(classes="compact-table", index=False, escape=False), unsafe_allow_html=True)

elif selected_view == "Minta azonosítók":
    st.title("Minta azonosítók")
    st.text_area("Minták")

# ===== EREDMÉNYEK =====
elif selected_view == "Táblázatos megjelenítés":
    st.title("Táblázatos megjelenítés")

elif selected_view == "PCR görbe megjelenítés":
    st.title("PCR görbe megjelenítés")






