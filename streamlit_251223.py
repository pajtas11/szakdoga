import streamlit as st
import pandas as pd


# Compatibility helper for Streamlit rerun across versions
def maybe_rerun():
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
            return
        except Exception:
            pass
    if hasattr(st, "rerun"):
        try:
            st.rerun()
            return
        except Exception:
            pass
    # Fallback: tell the user to refresh the page manually
    st.info("Frissítsd az oldalt (F5), hogy a változtatások érvénybe lépjenek.")

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
        maybe_rerun()

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
    
    # Standard 384-well: rows A-P (16 rows) and columns 1-24 (24 columns)
    rows = [chr(c) for c in range(ord("A"), ord("P") + 1)]
    cols = [str(i) for i in range(1, 25)]

    # Prepare a template DataFrame or load existing from session_state
    if "sample_grid_df" in st.session_state:
        grid_df = st.session_state["sample_grid_df"]
        # ensure correct shape/labels if user code changed earlier
        try:
            grid_df = grid_df.reindex(index=rows, columns=cols)
        except Exception:
            grid_df = pd.DataFrame("", index=rows, columns=cols)
    else:
        grid_df = pd.DataFrame("", index=rows, columns=cols)

    # --- Standard control selection (top) ---
    control_well_positions = [f"{r}{c}" for r in rows for c in cols]
    with st.expander("Standard kontrollok (helyek és mentés)", expanded=True):
        st.write("Kérjük adja meg a kontrollok számait és a poziciókat")
        n_pcr_ntc = st.number_input("PCR NTC darabszám", min_value=0, max_value=96, value=st.session_state.get("pcr_ntc_count", 1), key="pcr_ntc_count")
        n_pcr_pk = st.number_input("PCR PK darabszám", min_value=0, max_value=96, value=st.session_state.get("pcr_pk_count", 1), key="pcr_pk_count")
        n_prep_ntc = st.number_input("Prep NTC darabszám", min_value=0, max_value=96, value=st.session_state.get("prep_ntc_count", 1), key="prep_ntc_count")

        pcr_ntc_positions = []
        for i in range(int(n_pcr_ntc)):
            default = st.session_state.get(f"pcr_ntc_pos_{i}", control_well_positions[i] if i < len(control_well_positions) else control_well_positions[0])
            pos = st.selectbox(f"PCR NTC pozíció #{i+1}", options=control_well_positions, index=control_well_positions.index(default) if default in control_well_positions else 0, key=f"pcr_ntc_pos_{i}")
            pcr_ntc_positions.append(pos)

        pcr_pk_positions = []
        for i in range(int(n_pcr_pk)):
            default = st.session_state.get(f"pcr_pk_pos_{i}", control_well_positions[i+int(n_pcr_ntc)] if (i+int(n_pcr_ntc)) < len(control_well_positions) else control_well_positions[0])
            pos = st.selectbox(f"PCR PK pozíció #{i+1}", options=control_well_positions, index=control_well_positions.index(default) if default in control_well_positions else 0, key=f"pcr_pk_pos_{i}")
            pcr_pk_positions.append(pos)

        prep_ntc_positions = []
        for i in range(int(n_prep_ntc)):
            default = st.session_state.get(f"prep_ntc_pos_{i}", control_well_positions[i+int(n_pcr_ntc)+int(n_pcr_pk)] if (i+int(n_pcr_ntc)+int(n_pcr_pk)) < len(control_well_positions) else control_well_positions[0])
            pos = st.selectbox(f"Prep NTC pozíció #{i+1}", options=control_well_positions, index=control_well_positions.index(default) if default in control_well_positions else 0, key=f"prep_ntc_pos_{i}")
            prep_ntc_positions.append(pos)

        col_ctrl_save, col_ctrl_apply = st.columns([1, 1])
        if col_ctrl_save.button("Mentés kontrollok"):
            st.session_state["pcr_ntc_positions"] = pcr_ntc_positions
            st.session_state["pcr_pk_positions"] = pcr_pk_positions
            st.session_state["prep_ntc_positions"] = prep_ntc_positions
            st.success("Kontroll pozíciók elmentve.")

        if col_ctrl_apply.button("Alkalmaz standard neveket a rácsra"):
            # apply names into grid_df
            def apply_positions(positions, name_template):
                for idx, pos in enumerate(positions):
                    if not pos or len(pos) < 2:
                        continue
                    r = pos[0]
                    c = pos[1:]
                    label = name_template if len(positions) == 1 else f"{name_template} {idx+1}"
                    if (r in grid_df.index) and (c in grid_df.columns):
                        grid_df.at[r, c] = label

            apply_positions(pcr_ntc_positions, "PCR NTC")
            apply_positions(pcr_pk_positions, "PCR PK")
            apply_positions(prep_ntc_positions, "Prep NTC")
            st.session_state["sample_grid_df"] = grid_df
            st.success("Standard nevek alkalmazva és mentve a rácsban.")

    # If the user previously saved control positions, apply them into the grid so they are visible
    def _apply_saved_controls(df):
        mapping = [("pcr_ntc_positions", "PCR NTC"), ("pcr_pk_positions", "PCR PK"), ("prep_ntc_positions", "Prep NTC")]
        for key, label in mapping:
            positions = st.session_state.get(key, [])
            for idx, pos in enumerate(positions):
                if not pos or len(pos) < 2:
                    continue
                r = pos[0]
                c = pos[1:]
                label_str = label if len(positions) == 1 else f"{label} {idx+1}"
                if (r in df.index) and (c in df.columns):
                    df.at[r, c] = label_str

    _apply_saved_controls(grid_df)

    # Use available data-editor API if present, otherwise provide CSV fallback
    if hasattr(st, "experimental_data_editor"):
        data_editor_fn = st.experimental_data_editor
    elif hasattr(st, "data_editor"):
        data_editor_fn = st.data_editor
    else:
        data_editor_fn = None

    # Grid header instruction (visible above the editor)
    st.write("Kattints egy cellára és add meg a minta azonosítóját. Használd a Mentés gombot az eredmény tárolásához.")

    if data_editor_fn is not None:
        edited = data_editor_fn(grid_df, num_rows="fixed", key="sample_grid_editor")
    else:
        st.warning("A telepített Streamlit verzió nem támogatja az interaktív táblázat-szerkesztőt. CSV-feltöltéssel szerkesztheted a rácsot.")
        csv_bytes = grid_df.to_csv(index=True).encode("utf-8")
        st.download_button("Letöltés CSV sablon", csv_bytes, file_name="sample_grid_template.csv", mime="text/csv")
        uploaded = st.file_uploader("CSV feltöltése a rács frissítéséhez", type=["csv"])
        if uploaded:
            try:
                df_up = pd.read_csv(uploaded, index_col=0, dtype=str)
                df_up = df_up.reindex(index=rows, columns=cols).fillna("")
                edited = df_up
                st.success("CSV betöltve és rács frissítve.")
            except Exception as e:
                st.error(f"CSV betöltése sikertelen: {e}")
                edited = grid_df
        else:
            edited = grid_df

    

    # Persist the edited grid so it remains between interactions
    st.session_state["sample_grid_df"] = edited

    col1, col2 = st.columns([1, 1])
    if col1.button("Mentés"):
        records = []
        ncols = len(cols)
        for r_idx, r in enumerate(rows):
            for c_idx, c in enumerate(cols):
                sample_id = str(edited.at[r, c]).strip() if (r in edited.index and c in edited.columns) else ""
                well_number = r_idx * ncols + c_idx + 1
                well_position = f"{r}{c}"
                records.append({"well": well_number, "well_position": well_position, "sample_id": sample_id})

        long_df = pd.DataFrame(records)
        # Optionally drop empty sample_id rows - keep all wells for completeness
        # long_df = long_df[long_df['sample_id'].astype(bool)].reset_index(drop=True)

        st.session_state["samples_long_df"] = long_df
        st.success("Minták elmentve.")
        st.write(long_df)

    if col2.button("Reset beállítások"):
        # clear session state entries
        if "sample_grid_df" in st.session_state:
            del st.session_state["sample_grid_df"]
        if "samples_long_df" in st.session_state:
            del st.session_state["samples_long_df"]
        maybe_rerun()

    # If saved long-form DataFrame exists, display a small preview
    if "samples_long_df" in st.session_state:
        st.markdown("**Mentett eredmény (példa):**")
        st.write(st.session_state["samples_long_df"].head())

# ===== EREDMÉNYEK =====
elif selected_view == "Táblázatos megjelenítés":
    st.title("Táblázatos megjelenítés")

elif selected_view == "PCR görbe megjelenítés":
    st.title("PCR görbe megjelenítés")






