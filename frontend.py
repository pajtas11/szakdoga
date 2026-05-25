import streamlit as st
from pathlib import Path
import pandas as pd
import io
import plotly.express as px


from app.kits.kit_loader import load_available_kits
from app.kits.selected_kit import kit_info
from app.kits.selected_kit import load_selected_kit

from app.pcr.finalize_plate_layout import finalize_plate_layout
from app.pcr.data_loader import eds_extract

from app.output.controls_output import control_table, visual_PCR_curves_controls
from app.output.samples_output import visual_samples

from app.export.export import build_export_file
from app.pcr.evaluate_samples import evaluate_samples

from app.utils.plate_utils import (
    sample_id_df_to_grid,
    grid_to_sample_id_df,
    create_empty_plate_grid,
    clear_sample_id_state,
    load_basic_sample_ids,
    load_excel_sample_ids
)

st.set_page_config(
    page_title="PCR görbeértékelő alkalmazás",
    layout="wide"
)

st.title("PCR görbeértékelő alkalmazás")

# ----------------------------
# Opciók
# ----------------------------
INPUT_OPTIONS = ["Futási file", "PCR kit", "Minta azonosítók", "Kontrollok", "Összefoglaló"]
RESULT_OPTIONS = ["Kontrollok eredményei", "PCR görbe megjelenítés", "Táblázatos megjelenítés", "Export"]

# ----------------------------
# Session state init
# ----------------------------
st.session_state.setdefault("active_view", None)
st.session_state.setdefault("input", None)
st.session_state.setdefault("results", None)
st.session_state.setdefault("control_map", {})
st.session_state.setdefault("processed_file", None)
st.session_state.setdefault("final_layout", None)
st.session_state.setdefault("full_results", None)
st.session_state.setdefault("manual_overrides", {})
st.session_state.setdefault("accepted_wells", [])
st.session_state.setdefault("validated_wells", {})      # {well_position: datetime string}
st.session_state.setdefault("control_overrides", {})       # {well_position: {final_result, indok}}
st.session_state.setdefault("control_accepted_wells", []) # elfogadott kontroll well-ek

def get_target_options(kit_name: str) -> list[str]:
    """Visszaadja a kit összes lehetséges target kombinációját + üres értéket."""
    try:
        from app.kits.selected_kit import load_selected_kit
        from itertools import combinations
        kit = load_selected_kit(kit_name)[0]
        targets = [
            info["target_name"]
            for info in kit.get("targets", {}).values()
            if info.get("type") == "target"
        ]
        combos = [""]
        for r in range(1, len(targets) + 1):
            for combo in combinations(targets, r):
                combos.append(", ".join(combo))
        return combos
    except Exception:
        return [""]


def render_modify_panel(selected_well, selected_row, overrides, kit_name, accepted_wells_key="accepted_wells"):
    """Eredmény módosítása panel – selectbox final_result és target mezőkkel."""
    current_override = overrides.get(selected_well, {})
    current_final  = current_override.get("final_result", str(selected_row.get("final_result", "")))
    current_target = current_override.get("target",       str(selected_row.get("target", "")))
    current_ct     = current_override.get("ct",           str(selected_row.get("ct", "")))
    current_indok  = current_override.get("módosítás indoka", "")

    final_options = ["negatív", "pozitív"]
    final_index = final_options.index(current_final) if current_final in final_options else 0
    new_final = st.selectbox("final_result", options=final_options, index=final_index,
                              key=f"edit_final_{selected_well}")

    target_options = get_target_options(kit_name)
    target_index = target_options.index(current_target) if current_target in target_options else 0
    new_target = st.selectbox("target", options=target_options, index=target_index,
                               key=f"edit_target_{selected_well}")

    new_ct    = st.text_input("ct", value=current_ct, key=f"edit_ct_{selected_well}")
    new_indok = st.text_area("Módosítás indoka *", value=current_indok,
                              key=f"edit_indok_{selected_well}", help="Kötelező mező a mentéshez")

    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("Mentés", key=f"save_{selected_well}", width='stretch'):
            if not new_indok.strip():
                st.error("A módosítás indoka kötelező!")
            else:
                st.session_state["manual_overrides"][selected_well] = {
                    "final_result":     new_final,
                    "target":           new_target,
                    "ct":               new_ct,
                    "módosítás indoka": new_indok
                }
                if selected_well in st.session_state[accepted_wells_key]:
                    st.session_state[accepted_wells_key].remove(selected_well)
                st.session_state["full_results"] = None
                st.success("Módosítás elmentve!")
                st.rerun()
    with col_reset:
        if st.button("Visszaállítás", key=f"reset_{selected_well}", width='stretch'):
            st.session_state["manual_overrides"].pop(selected_well, None)
            if selected_well in st.session_state[accepted_wells_key]:
                st.session_state[accepted_wells_key].remove(selected_well)
            st.session_state["full_results"] = None
            st.success("Eredeti érték visszaállítva!")
            st.rerun()


def on_input_change():
    """Ha bemeneti menüben választottak, töröljük az eredmény választást."""
    st.session_state["active_view"] = st.session_state.get("input")
    st.session_state["results"] = None

def on_results_change():
    """Ha eredmény menüben választottak, töröljük a bemeneti választást."""
    st.session_state["active_view"] = st.session_state.get("results")
    st.session_state["input"] = None

# ==============================
# SIDEBAR
# ==============================
st.sidebar.header("Menü")

with st.sidebar.expander("Bemeneti adatok", expanded=True):
    st.radio(
        "Bemeneti adatok",
        INPUT_OPTIONS,
        index=INPUT_OPTIONS.index(st.session_state["input"])
        if st.session_state["input"] in INPUT_OPTIONS else None,
        key="input",
        on_change=on_input_change,
        label_visibility="collapsed"
    )

with st.sidebar.expander("Eredmények", expanded=True):
    st.radio(
        "Eredmények",
        RESULT_OPTIONS,
        index=RESULT_OPTIONS.index(st.session_state["results"])
        if st.session_state["results"] in RESULT_OPTIONS else None,
        key="results",
        on_change=on_results_change,
        label_visibility="collapsed"
    )

selected_view = st.session_state.get("active_view")

# ==============================
# OLDAL TARTALOM
# ==============================
if selected_view is None:
    st.write("Válassz funkciót a bal oldali menüből.")

# ==============================
# Futási file
# ==============================

elif selected_view == "Futási file":


    st.header("Futási file feltöltése")

    # -----------------------
    # Session init
    # -----------------------
    st.session_state.setdefault("eds_name", None)
    st.session_state.setdefault("eds_bytes", None)
    st.session_state.setdefault("raw_df", None)
    st.session_state.setdefault("eds_uploader_key_counter", 0)
    st.session_state.setdefault("eds_uploader_key", "eds_uploader_0")
    #st.session_state.setdefault("channels", None)

    # -----------------------
    # Feltöltő
    # -----------------------
    uploaded = st.file_uploader(
        "EDS fájl kiválasztása",
        key=st.session_state["eds_uploader_key"]
    )

    # -----------------------
    # ÚJ feltöltés feldolgozása
    # -----------------------
 
    if uploaded is not None and st.session_state["processed_file"] != uploaded.name:
        with st.spinner(f"Fájl feldolgozása: {uploaded.name}..."):
            try:
                # Fájl tartalmának beolvasása memóriába
                st.session_state["eds_bytes"] = uploaded.getvalue()
                file_like = io.BytesIO(st.session_state["eds_bytes"])
                
                # Backend feldolgozás
                raw_df = eds_extract(file_like)
                
                # Eredmények mentése session state-be
                st.session_state["raw_df"] = raw_df
                st.session_state["eds_name"] = uploaded.name
                st.session_state["processed_file"] = uploaded.name # Ezzel jelezzük, hogy kész
                
                st.success(f"Fájl sikeresen betöltve: {uploaded.name}")
            except Exception as e:
                st.error(f"Hiba a feldolgozás során: {e}")
                st.session_state["raw_df"] = None
                st.session_state["processed_file"] = None


    # -----------------------
    # Állapotjelző (akkor is, ha a file_uploader üres)
    # -----------------------
    if st.session_state.get("eds_name") and st.session_state.get("eds_bytes"):
        name = st.session_state["eds_name"]
        size_kb = len(st.session_state["eds_bytes"]) / 1024

        st.info(f"✅ Jelenleg betöltött futási file: **{name}**  ({size_kb:.1f} KB)")

        # Törlés gomb
        if st.button("Feltöltött fájl törlése"):
            st.session_state["eds_name"] = None
            st.session_state["eds_bytes"] = None
            st.session_state["raw_df"] = None
            st.session_state["channels"] = None
            st.session_state["processed_file"] = None

            # A file_uploader widget újraindításához új key-t használunk.
            st.session_state["eds_uploader_key_counter"] += 1
            st.session_state["eds_uploader_key"] = (
                f"eds_uploader_{st.session_state['eds_uploader_key_counter']}"
            )
            st.rerun()
    else:
        st.warning("⚠️ Még nincs betöltött futási file. Kérlek tölts fel egy EDS fájlt.")

    st.divider()

    # -----------------------
    # Preview (session_state-ből)
    # -----------------------
    df = st.session_state.get("raw_df")
    if df is not None:
        st.subheader("Nyers adatok (előnézet)")
        st.dataframe(df.head(200), width='stretch')

        # opcionális: csatornák kijelzése
        if st.session_state.get("channels") is not None:
            st.caption(f"Detektált csatornák: {st.session_state['channels']}")
    else:
        if st.session_state.get("eds_name"):
            st.error("A fájl betöltve, de a nyers adatok nem készültek el (eds_extract nem adott vissza DataFrame-et).")

# ==============================
# PCR kit
# ==============================

elif selected_view == "PCR kit":
    st.header("PCR kit kiválasztása")
    st.divider()
    st.caption("Elérhető PCR kitek")

    kits = load_available_kits()  # list[str]

    # Session init
    st.session_state.setdefault("selected_kit", None)

    # Készítünk egy "placeholder" opciót, hogy lehessen "nincs kiválasztva" állapot
    options = ["— Válassz PCR kitet —"] + kits

    # Alapértelmezett index: ha már volt választás, arra állunk rá
    if st.session_state["selected_kit"] in kits:
        default_index = options.index(st.session_state["selected_kit"])
    else:
        default_index = 0

    picked = st.selectbox(
        "PCR kit",
        options,
        index=default_index,
        key="selected_kit_selectbox"
    )

    # Csak akkor mentjük, ha tényleg kit lett választva (nem a placeholder)
    if picked != "— Válassz PCR kitet —":
        st.session_state["selected_kit"] = picked

    selected_kit = st.session_state.get("selected_kit")

    st.divider()

    if selected_kit:
        st.success(f"Kiválasztott kit: {selected_kit}")
    else:
        st.info("Még nincs kiválasztott PCR kit.")
        # Ne próbáljunk táblát rajzolni
        selected_kit = None

    # Kit paraméterek megjelenítése csak akkor, ha van választás
    if selected_kit:
        df = kit_info(selected_kit)

        st.markdown("""
        <style>
        .compact-table table { width: auto !important; }
        .compact-table th { text-align: center !important; }
        .compact-table td { text-align: left; }
        .compact-table th, .compact-table td {
            padding: 6px 12px;
            white-space: nowrap;
        }
        </style>
        """, unsafe_allow_html=True)

        if df is None:
            st.info("Válassz PCR kitet a fenti listából.")
        else:
            st.markdown(df.to_html(classes="compact-table", index=False), unsafe_allow_html=True)

# ==============================
# Minta azonosítók
# ==============================

elif selected_view == "Minta azonosítók":

    st.header("Mintaazonosítók")


    # --------------------------------------------------
    # Leírás
    # --------------------------------------------------
    st.markdown("### A mintaazonosítók kezelése két módon lehetséges:")

    st.markdown("""
        **1. Általános mintaazonosítók használata**

        Ebben az esetben az alkalmazás egy előre elkészített mintaazonosító listát tölt be
        (`Sample1`–`Sample384`).
        Ez akkor hasznos, ha még nincs végleges mintaazonosító lista, vagy gyorsan szeretnél elindulni az elemzéssel.

        **2. Excel sablon feltöltése**

        A mintaazonosítók egy Excel sablon segítségével adhatók meg, amely tartalmaz egy
        `384well_plate` munkalapot, ahol a well position szerint kell megadni a minták azonosítóját.
        """)

    template_path = Path("app/templates/sample_id_template.xlsx")

    col1, col2 = st.columns([1, 3])

    with col1:
        if template_path.exists():
            with open(template_path, "rb") as f:
                template_bytes = f.read()

            st.download_button(
                label="Excel sablon letöltése",
                data=template_bytes,
                file_name="sample_id_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("A sablonfájl nem található.")

    st.divider()

    st.session_state.setdefault("reset_sample_id_widgets", False)

    if st.session_state.get("reset_sample_id_widgets"):
        st.session_state.pop("sample_id_mode", None)
        st.session_state.pop("sample_id_excel_uploader", None)
        st.session_state["reset_sample_id_widgets"] = False

    # --------------------------------------------------
    # Mód kiválasztása
    # --------------------------------------------------
    sample_id_mode = st.radio(
        "Mintaazonosítók megadásának módja",
        [
            "Általános mintaazonosítók használata",
            "Excel sablon feltöltése"
        ],
        index=0,
        key="sample_id_mode",
    )

    # --------------------------------------------------
    # 1. opció: általános mintaazonosítók
    # --------------------------------------------------
    if sample_id_mode == "Általános mintaazonosítók használata":
        st.info("Az előre elkészített mintaazonosító lista betöltéséhez kattints a gombra.")

        if st.button("Általános mintaazonosítók betöltése"):
            load_basic_sample_ids()

    # --------------------------------------------------
    # 2. opció: Excel sablon feltöltése
    # --------------------------------------------------
    elif sample_id_mode == "Excel sablon feltöltése":
        st.write("Töltsd fel a kitöltött Excel sablont.")

        uploaded_sample_file = st.file_uploader(
            "Excel sablon feltöltése",
            type=["xlsx"],
            key="sample_id_excel_uploader",
        )

        if uploaded_sample_file is not None:
            if st.button("Feltöltött Excel beolvasása", width='stretch'):
                load_excel_sample_ids(uploaded_sample_file)

    st.divider()

    # --------------------------------------------------
    # Aktuális állapot
    # --------------------------------------------------
    current_file = st.session_state.get("sample_id_file_name")
    current_sample_df = st.session_state.get("sample_id_df")

    if current_file:
        st.info(f"Jelenleg használt mintaazonosító forrás: {current_file}")

    st.subheader("384 well plate szerkesztése")

    if current_sample_df is not None:
        try:
            editable_grid = sample_id_df_to_grid(current_sample_df)
        except Exception as e:
            st.error(f"A sample_id_df nem alakítható grid formára: {e}")
            editable_grid = create_empty_plate_grid()
    else:
        editable_grid = create_empty_plate_grid()

    edited_grid = st.data_editor(
        editable_grid,
        width='stretch',
        num_rows="fixed",
        key="sample_id_plate_editor"
        )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Grid módosítások mentése", width='stretch'):
            try:
                updated_sample_id_df = grid_to_sample_id_df(edited_grid)
                st.session_state["sample_id_df"] = updated_sample_id_df
                st.success("A mintaazonosítók frissítése sikeresen mentve.")
                st.rerun()
            except Exception as e:
                st.error(f"A grid mentése nem sikerült: {e}")

    with col2:
        if st.button("Grid kiürítése", width='stretch'):
            st.session_state["sample_id_df"] = grid_to_sample_id_df(create_empty_plate_grid())
            st.success("A 384 grid kiürítve.")
            st.rerun()

    # opcionális preview long formában
    if st.session_state.get("sample_id_df") is not None:
        with st.expander("Sample_ID adatok long formában", expanded=False):
            st.dataframe(st.session_state["sample_id_df"])

    # --------------------------------------------------
    # Törlés
    # --------------------------------------------------
    if current_sample_df is not None:
        if st.button("Mintaazonosítók törlése", type="secondary"):
            clear_sample_id_state()
            st.session_state["reset_sample_id_widgets"] = True
            st.rerun()

# ==============================
# Kontrollok
# A kontrollok pozíciójának megadása: 
#  - kontrollok meghatározása selected_kit alapján, illetve Prep NTC 
#  - a pozició megadáskor csak az eds file-ba található well_position-ből választhat a felhasználó
# ==============================

elif selected_view == "Kontrollok":
    st.header("Kontrollok kijelölése")

    # 1. Ellenőrizzük, van-e választott kit
    selected_kit_name = st.session_state.get("selected_kit")

    if not selected_kit_name:
        st.warning("⚠️ Előbb válassz egy PCR kitet a 'PCR kit' menüpontban!")
    else:
        # 2. Kit-specifikus kontrollok betöltése a backendből
        # A megadott load_selected_kit függvény [3]-as indexű eleme a kontroll lista
        
        try:
            kit_data = load_selected_kit(selected_kit_name)
            base_controls = list(kit_data[3])  # Pl. ["NTC", "PTC"]
        except Exception as e:
            st.error(f"Hiba a kit adatainak betöltésekor: {e}")
            base_controls = []

        st.subheader(f"Választott kit: {selected_kit_name}")
        
        # 3. Prep_NTC opció kezelése
        has_prep_ntc = st.checkbox("Van a futásban Prep_NTC (extrakciós kontroll)?", key="has_prep_ntc")
        
        # Végleges kontroll lista összeállítása
        final_control_options = base_controls.copy()
        if has_prep_ntc and "Prep_NTC" not in final_control_options:
            final_control_options.append("Prep_NTC")

        st.divider()

        # 4. Kontrollok elhelyezése a plate-en eds-ből vett well_position alapján
        col1, col2 = st.columns(2)
        
        with col1:
            selected_type = st.selectbox(
                "Kontrollok",
                options=final_control_options
            )

        with col2:
            raw_df = st.session_state.get("raw_df")

            if raw_df is not None:
                available_wells = sorted(
                    raw_df['well_position'].unique(),
                    key=lambda x: (ord(x[0]), int(x[1:]))
                )
                st.success(f"Az EDS fájl alapján {len(available_wells)} mért well közül választhatsz.")
                selected_wells = st.multiselect(
                    f"Wells a(z) {selected_type} kontrollhoz",
                    options=available_wells,
                    key=f"wells_input_{selected_type}"
                )
            else:
                available_wells = []
                selected_wells = []
                st.warning("⚠️ Nincs betöltött EDS fájl! Kérlek, előbb töltsd fel a futási fájlt a 'Futási file' menüpontban.")

        if st.button("Kijelölt kontrollok mentése"):
            if selected_wells:
                for well in selected_wells:
                    st.session_state["control_map"][well] = selected_type
                st.success(f"Mentve: {selected_type} -> {', '.join(selected_wells)}")
            else:
                st.warning("Válassz legalább egy well-t!")

        # 5. Állapot megjelenítése
        if st.session_state["control_map"]:
            st.divider()
            st.subheader("Aktuális kontroll kiosztás")
            
            # Táblázatos nézet a kontrollokról
            ctrl_summary = pd.DataFrame([
                {"Well_position": k, "Kontroll típusa": v} for k, v in st.session_state["control_map"].items()
            ])
            st.table(ctrl_summary.sort_values("Well_position"))

            if st.button("Összes kontroll törlése", type="secondary"):
                st.session_state["control_map"] = {}
                st.rerun()

# ==============================
# Összefoglaló
# ==============================


elif selected_view == "Összefoglaló":
    st.header("Összefoglaló")
    st.info("Az elemzés megkezdése előtt ellenőrizd, hogy minden szükséges adatot megadtál-e.")

    # 1. Státuszok kiszámítása
    eds_ready = st.session_state.get("raw_df") is not None
    kit_ready = st.session_state.get("selected_kit") is not None
    samples_ready = st.session_state.get("sample_id_df") is not None
    # Megnézzük, van-e legalább egy elem a kontroll térképben
    controls_ready = len(st.session_state.get("control_map", {})) > 0

    # 2. Megjelenítés egymás alatt (Vertical List)
    st.markdown("### Állapotellenőrzés")
    
    # Futási fájl
    if eds_ready:
        st.write(f"✅ **Futási fájl:** {st.session_state.get('eds_name')}")
    else:
        st.write("❌ **Futási fájl:** Nincs feltöltve")

    # PCR Kit
    if kit_ready:
        st.write(f"✅ **PCR Kit:** {st.session_state.get('selected_kit')}")
    else:
        st.write("❌ **PCR Kit:** Nincs kiválasztva")

    # Mintaazonosítók
    if samples_ready:
        st.write(f"✅ **Mintaazonosítók:** Betöltve ({len(st.session_state['sample_id_df'])} well)")
    else:
        st.write("❌ **Mintaazonosítók:** Hiányzik")

    # Kontrollok
    if controls_ready:
        st.write(f"✅ **Kontrollok:** {len(st.session_state['control_map'])} pozíció rögzítve")
    else:
        st.write("⚠️ **Kontrollok:** Nincs kijelölve egyetlen kontroll sem (opcionális, de javasolt)")

    st.divider()

    # 3. Véglegesítési logika
    if eds_ready and kit_ready and samples_ready:
        st.success("Minden kötelező adat rendelkezésre áll.")
        
        if st.button("ADATOK VÉGLEGESÍTÉSE ÉS ELEMZÉS INDÍTÁSA", type="primary", width='stretch'):
            from app.pcr.finalize_plate_layout import finalize_plate_layout
            
            # Layout összefűzése
            st.session_state["final_layout"] = finalize_plate_layout(
                st.session_state["sample_id_df"], 
                st.session_state["control_map"]
            )
            
            # Itt jelezzük a sikerességet
            #st.balloons()
            st.success("A plate layout elkészült! Most már átléphetsz az 'Eredmények' menüpontokhoz.")
    else:
        st.error("⚠️ Kérlek, pótold a hiányzó adatokat a fenti pontok alapján!")

# ==============================
# Kontrollok eredményei
# ==============================

elif selected_view == "Kontrollok eredményei":
    st.header("Kontroll eredmények ellenőrzése")

    eds_bytes = st.session_state.get("eds_bytes")
    final_layout = st.session_state.get("final_layout")
    kit_name = st.session_state.get("selected_kit")

    if eds_bytes is None or final_layout is None or kit_name is None:
        st.warning("⚠️ Hiányzó adatok! Kérlek, előbb töltsd fel az EDS fájlt és véglegesítsd a layoutot az 'Összefoglaló' fülön.")
    else:
        try:
            file_for_backend = io.BytesIO(eds_bytes)
            df_controls_result = control_table(
                file=file_for_backend,
                sampleid_df=final_layout,
                selected_kit_name=kit_name
            )

            if df_controls_result is None or df_controls_result.empty:
                st.info("Nincsenek megjeleníthető kontroll adatok.")
            else:
                # Manuális override-ok alkalmazása
                ctrl_overrides = st.session_state["control_overrides"]
                ctrl_accepted  = st.session_state["control_accepted_wells"]
                df_controls_display = df_controls_result.copy()
                for wp, changes in ctrl_overrides.items():
                    mask = df_controls_display["well_position"] == wp
                    if "final_result" in changes:
                        df_controls_display.loc[mask, "final_result"] = changes["final_result"]

                # Elfogadva oszlop
                df_controls_display["Elfogadva"] = df_controls_display["well_position"].map(
                    lambda wp: wp in ctrl_accepted
                )

                # --- TÁBLÁZAT – sorra kattintható ---
                st.subheader("Kontroll statisztika")

                st.write("Kattints egy sorra a görbe és módosítás megjelenítéséhez:")

                ctrl_selection = st.dataframe(
                    df_controls_display,
                    width='stretch',
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="ctrl_row_selector"
                )

                col_ctrl_unaccept, _ = st.columns([1, 3])
                with col_ctrl_unaccept:
                    if st.button("↩️ Összes elfogadás visszavonása", width='stretch'):
                        st.session_state["control_accepted_wells"] = []
                        st.success("Összes kontroll elfogadás visszavonva!")
                        st.rerun()

                ctrl_selected_rows = ctrl_selection["selection"]["rows"] if ctrl_selection else []

                if ctrl_selected_rows:
                    ctrl_row_index = ctrl_selected_rows[0]
                    ctrl_row = df_controls_display.iloc[ctrl_row_index]
                    ctrl_well = ctrl_row["well_position"]
                    ctrl_sample_id = str(ctrl_row.get("sample_id", ""))
                    ctrl_current_result = str(ctrl_row.get("final_result", ""))

                    st.divider()
                    col_chart, col_edit = st.columns([2, 1])

                    # --- GÖRBE ---
                    with col_chart:
                        st.subheader(f"PCR görbe – {ctrl_sample_id} ({ctrl_well})")
                        try:
                            file_for_viz = io.BytesIO(eds_bytes)
                            fig_controls = visual_PCR_curves_controls(
                                file=file_for_viz,
                                sampleid_df=final_layout,
                                selected_kit_name=kit_name,
                                controls_table=df_controls_result,
                                control_name=ctrl_sample_id
                            )
                            if fig_controls is not None:
                                st.plotly_chart(fig_controls, width='stretch')
                            else:
                                st.info("A vizualizáció nem elérhető.")
                        except Exception as e:
                            st.error(f"Hiba a görbe betöltésekor: {e}")

                    # --- MÓDOSÍTÁS PANEL ---
                    with col_edit:
                        current_override = ctrl_overrides.get(ctrl_well, {})
                        current_result = current_override.get("final_result", ctrl_current_result)
                        current_indok  = current_override.get("indok", "")

                        action = st.radio(
                            "Döntés:",
                            options=["Elfogad", "Módosít"],
                            key=f"ctrl_action_{ctrl_well}"
                        )

                        if action == "Elfogad":
                            st.subheader("Elfogadás")
                            is_ctrl_accepted = ctrl_well in ctrl_accepted
                            if not is_ctrl_accepted:
                                if st.button("Elfogadás mentése", key=f"ctrl_accept_{ctrl_well}",
                                             width='stretch'):
                                    if ctrl_well not in st.session_state["control_accepted_wells"]:
                                        st.session_state["control_accepted_wells"].append(ctrl_well)
                                    st.session_state["control_overrides"].pop(ctrl_well, None)
                                    st.success("Elfogadva!")
                                    st.rerun()
                            else:
                                st.success(f"✅ Elfogadva")
                                if st.button("↩️ Elfogadás visszavonása", key=f"ctrl_unaccept_{ctrl_well}",
                                             width='stretch'):
                                    st.session_state["control_accepted_wells"].remove(ctrl_well)
                                    st.rerun()

                        else:  # Módosít
                            st.subheader("Eredmény módosítása")

                            # Lehetséges értékek: Valid/Invalid a kontroll nevével
                            result_options = [
                                f"Valid {ctrl_sample_id}",
                                f"Invalid {ctrl_sample_id}"
                            ]
                            result_index = result_options.index(current_result)                                 if current_result in result_options else 0

                            new_result = st.selectbox(
                                "final_result",
                                options=result_options,
                                index=result_index,
                                key=f"ctrl_result_{ctrl_well}"
                            )
                            new_indok = st.text_area(
                                "Módosítás indoka *",
                                value=current_indok,
                                key=f"ctrl_indok_{ctrl_well}",
                                help="Kötelező mező a mentéshez"
                            )

                            col_save, col_reset = st.columns(2)
                            with col_save:
                                if st.button("Mentés", key=f"ctrl_save_{ctrl_well}",
                                             width='stretch'):
                                    if not new_indok.strip():
                                        st.error("A módosítás indoka kötelező!")
                                    else:
                                        st.session_state["control_overrides"][ctrl_well] = {
                                            "final_result": new_result,
                                            "indok":        new_indok
                                        }
                                        if ctrl_well in st.session_state["control_accepted_wells"]:
                                            st.session_state["control_accepted_wells"].remove(ctrl_well)
                                        st.success("Módosítás elmentve!")
                                        st.rerun()
                            with col_reset:
                                if st.button("Visszaállítás", key=f"ctrl_reset_{ctrl_well}",
                                             width='stretch'):
                                    st.session_state["control_overrides"].pop(ctrl_well, None)
                                    st.success("Eredeti érték visszaállítva!")
                                    st.rerun()
                else:
                    st.info("Jelölj ki egy sort a táblázatban a görbe és módosítás megjelenítéséhez.")

        except Exception as e:
            st.error(f"Hiba történt a kontrollok feldolgozása során: {e}")

# ==============================
# PCR görbe megjelenítés
# ==============================

elif selected_view == "PCR görbe megjelenítés":
    st.header("Interaktív PCR Eredmények")

    # Adatok betöltése
    eds_bytes = st.session_state.get("eds_bytes")
    raw_df = st.session_state.get("raw_df")
    final_layout = st.session_state.get("final_layout")
    kit_name = st.session_state.get("selected_kit")

    if eds_bytes is None or final_layout is None or raw_df is None:
        st.warning("⚠️ Hiányzó adatok! Töltsd fel a fájlt és véglegesítsd a layoutot.")
    else:
        try:
            from app.pcr.evaluate_samples import evaluate_samples
            file_buf = io.BytesIO(eds_bytes)
            backend_layout = final_layout.copy()

            # session_state-ből vesszük ha már kiszámolt, különben újraszámoljuk
            if st.session_state["full_results"] is not None:
                full_results = st.session_state["full_results"].copy()
            else:
                full_results = evaluate_samples(file_buf, backend_layout, kit_name)

            # Manuális módosítások alkalmazása
            overrides = st.session_state.get("manual_overrides", {})
            for wp, changes in overrides.items():
                mask = full_results["well_position"] == wp
                for col, val in changes.items():
                    if col in full_results.columns:
                        full_results.loc[mask, col] = val

        except Exception as e:
            st.error(f"Hiba az értékelés során: {e}")
            st.stop()

        col_plot, col_plate = st.columns([1, 1.2])

        # Session state inicializálása
        if "selected_well_visual" not in st.session_state:
            st.session_state["selected_well_visual"] = None

        # --- JOBB OLDAL: PLATE GRID ---
        with col_plate:
            with st.container(border=True):
                st.subheader("384-Well Plate")
            
                rows = list("ABCDEFGHIJKLMNOP") # A-P
                cols = [str(i) for i in range(1, 25)] 
            
                # ADAT-NORMALIZÁLÁS: Biztosítjuk, hogy az A1 és A01 is egyezzen
                measured_wells = set(raw_df['well_position'].unique())
            
                grid_data = []
                for r in rows:
                    for c in cols:
                        pos = f"{r}{c}"
                        # Ellenőrizzük a vezető nullás formátumot is (pl. A1 -> A01)
                        pos_alt = f"{r}{int(c):02d}"
                    
                        res_row = full_results[full_results['well_position'] == pos]
                        if res_row.empty: # Ha nincs meg simán, próbáljuk a nullás verzióval
                            res_row = full_results[full_results['well_position'] == pos_alt]
                    
                        status = "Nincs mérés"
                        color = "#363636" # szürke
                    
                        # Ha az EDS fájlban van jel ehhez a well-hez
                        if pos in measured_wells or pos_alt in measured_wells:
                            status = "Mért (adat van)"
                            color = "#D3D3D3" # fehér
                    
                        if not res_row.empty:
                            row = res_row.iloc[0]
                            if row.get('sample_id') == 'NTC' or row.get('sample_id') == 'PK' or row.get('sample_id') == 'Prep_NTC':
                                status = "Kontroll"
                                color = "#3498db"
                            elif not row.get('valid', True):
                                status = "Invalid"
                                color = "#e74c3c"
                            elif row.get('final_result') in ['pozitív', 'Positive']:
                                status = "Pozitív"
                                color = "#e67e22"
                            elif row.get('final_result') in ['negatív', 'Negative']:
                                status = "Negatív"
                                color = "#2ecc71"
                    
                        grid_data.append({"Sor": r, "Oszlop": c, "Well": pos, "Állapot": status, "Szín": color})
            
                df_grid = pd.DataFrame(grid_data)

                # Grafikon összeállítása
                fig_grid = px.scatter(
                    df_grid, x="Oszlop", y="Sor", color="Állapot",
                    hover_name="Well",
                    # Kategória sorrend kényszerítése (A-tól P-ig)
                    category_orders={"Sor": rows, "Oszlop": cols},
                    color_discrete_map={
                        "Nincs mérés": "#363636", "Mért (adat van)": "#D3D3D3",
                        "Invalid": "#e74c3c", "Negatív": "#2ecc71",
                        "Pozitív": "#e67e22", "Kontroll": "#3498db"
                    }
                )
            
                fig_grid.update_traces(marker=dict(size=16, symbol="square", line=dict(width=0.5, color="black")))

                fig_grid.update_layout(
                    clickmode='event+select',
                    xaxis=dict(
                        side='top', type='category', title="",
                        tickfont=dict(size=10),
                        fixedrange=True
                    ),
                    yaxis=dict(
                        type='category', title="",
                        categoryorder='array', categoryarray=rows,
                        autorange="reversed",
                        tickfont=dict(size=10),
                        fixedrange=True
                    ),
                    showlegend=True,
                    height=600,
                    autosize=True,
                    margin=dict(l=20, r=20, b=20, t=40)
                )

                # Kattintás figyelése
                # FONTOS: Nem használunk manuális st.rerun()-t a blokkon belül!
                event = st.plotly_chart(fig_grid, on_select="rerun", width='stretch', key="plate_chart")

                # Ha a felhasználó kattintott, frissítjük a session state-et
                if event and "selection" in event and event["selection"]["points"]:
                    clicked_well = event["selection"]["points"][0]["hovertext"]
                    if st.session_state["selected_well_visual"] != clicked_well:
                        st.session_state["selected_well_visual"] = clicked_well
            
                if st.button("Kijelölés törlése"):
                    st.session_state["selected_well_visual"] = None
                    st.rerun()

        # --- BAL OLDAL: GÖRBÉK ---
        with col_plot:
            with st.container(border=True): # Ez adja a keretet
                current_well = st.session_state["selected_well_visual"]
            
                if current_well:
                    st.subheader(f"Well görbe: {current_well}")
                    try:
                        # Figyelj a fájlnévre: korábban sample_output-ot írtunk!
                        from app.output.samples_output import visual_samples
                        file_buf_viz = io.BytesIO(eds_bytes)
                        fig_s = visual_samples(file_buf_viz, backend_layout, kit_name, current_well)
                        if fig_s:
                            st.plotly_chart(fig_s, width='stretch')
                    except Exception as e:
                        st.error(f"Hiba a görbe megjelenítésekor: {e}")
                else:
                    st.subheader("Összesített görbék")
                    from app.pcr.sampleid_mapping import mapping_sampleid
                    file_buf_all = io.BytesIO(eds_bytes)
                    signals = mapping_sampleid(file_buf_all, backend_layout)
                    channels = load_selected_kit(kit_name)[2]
                
                    fig_all = px.line(
                        signals, x="cycle", y=channels, color="well_position",
                        title="Minden minta és kontroll", template="plotly_white"
                    )
                    fig_all.update_layout(showlegend=False)
                    st.plotly_chart(fig_all, width='stretch')


# ==============================
# Táblázatos megjelenítés
# ==============================
elif selected_view == "Táblázatos megjelenítés":
    st.header("Eredmények táblázatos formában")

    eds_bytes = st.session_state.get("eds_bytes")
    final_layout = st.session_state.get("final_layout")
    kit_name = st.session_state.get("selected_kit")

    if eds_bytes is None or final_layout is None:
        st.warning("Hiányzó adatok! Kérlek, előbb töltsd fel az EDS fájlt és véglegesítsd a layoutot.")
    else:
        # 1. ADATOK ELŐKÉSZÍTÉSE
        try:
            from app.pcr.evaluate_samples import evaluate_samples
            file_buf = io.BytesIO(eds_bytes)

            backend_layout = final_layout.copy()
            if 'sample_id' in backend_layout.columns and 'sampleid' not in backend_layout.columns:
                backend_layout['sampleid'] = backend_layout['sample_id']
            elif 'sampleid' in backend_layout.columns and 'sample_id' not in backend_layout.columns:
                backend_layout['sample_id'] = backend_layout['sampleid']

            # Csak egyszer futtatjuk, utána session_state-ből olvassuk
            if st.session_state["full_results"] is None:
                full_results = evaluate_samples(file_buf, backend_layout, kit_name)
                st.session_state["full_results"] = full_results.copy()
            else:
                full_results = st.session_state["full_results"].copy()

            # Manuális módosítások alkalmazása
            overrides = st.session_state["manual_overrides"]
            accepted_wells = st.session_state["accepted_wells"]

            for wp, changes in overrides.items():
                mask = full_results["well_position"] == wp
                for col, val in changes.items():
                    if col in full_results.columns:
                        full_results.loc[mask, col] = val
                # flag: "Manuálisan módosítva: {indok}"
                if "flag" in full_results.columns:
                    indok = changes.get("módosítás indoka", "")
                    full_results.loc[mask, "flag"] = f"Manuálisan módosítva: {indok}"

            # Elfogadott sorok flag frissítése
            for wp in accepted_wells:
                mask = full_results["well_position"] == wp
                if "flag" in full_results.columns:
                    full_results.loc[mask, "flag"] = "Elfogadva"

            # Validálva oszlop hozzáadása: False vagy validálás dátuma
            validated_wells_map = st.session_state["validated_wells"]
            full_results["Validálva"] = full_results["well_position"].map(
                lambda wp: validated_wells_map.get(wp, False)
            )

            display_cols = ['well', 'well_position', 'sample_id', 'final_result', 'target', 'ct', 'flag', 'Validálva']
            existing_cols = [c for c in display_cols if c in full_results.columns]
            df_display = full_results[existing_cols]

        except Exception as e:
            st.error(f"Hiba az adatok feldolgozása során: {e}")
            st.stop()

        # 2. SZŰRŐK
        col1, col2 = st.columns(2)
        with col1:
            show_flagged = st.checkbox("Csak manuális értékelést igénylő sorok", value=False)
        with col2:
            show_positive = st.checkbox("Csak pozitív target-tel rendelkező sorok", value=False)

        df_filtered = df_display.copy()
        if show_flagged and "flag" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["flag"].str.strip() != ""]
        if show_positive and "target" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["target"].str.strip() != ""]

        # 3. TÁBLÁZAT – sorra kattintva görbe + módosítás, pipával validálás
        validated_wells = st.session_state["validated_wells"]

        # Validálás csak akkor engedélyezett, ha minden kontroll el van fogadva
        ctrl_accepted = st.session_state.get("control_accepted_wells", [])
        minden_kontroll_elfogadva = len(ctrl_accepted) > 0

        validalhato_wells = [
            wp for wp in df_filtered["well_position"].tolist()
            if str(df_filtered.loc[df_filtered["well_position"] == wp, "flag"].values[0]).strip() != "manuális értékelést igényel"
        ] if minden_kontroll_elfogadva else []

        if not minden_kontroll_elfogadva:
            st.warning("⚠️ A validálás nem lehetséges: előbb fogadd el az összes kontrollt a **Kontrollok eredményei** fülön.")

        st.write("Kattints egy sorra a görbe és módosítás megjelenítéséhez:")

        # Egyetlen táblázat – sorkijelöléssel
        selection = st.dataframe(
            df_filtered,
            width='stretch',
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="row_selector"
        )

        # Összes validálható sor validálása / visszavonása
        col_val_all, col_unval_all, _ = st.columns([1, 1, 3])
        with col_val_all:
            if st.button("☑ Összes validálása", width='stretch'):
                from datetime import datetime
                now = datetime.now().strftime("%Y.%m.%d. %H:%M")
                for wp in validalhato_wells:
                    st.session_state["validated_wells"][wp] = now
                st.success(f"{len(validalhato_wells)} sor sikeresen validálva ({now})!")
                st.rerun()
        with col_unval_all:
            if st.button("↩️ Összes visszavonása", width='stretch'):
                st.session_state["validated_wells"] = {}
                st.session_state["full_results"] = None
                st.success("Összes validálás visszavonva!")
                st.rerun()

        # 4. KIJELÖLT SOR – GÖRBE + DÖNTÉS + VALIDÁLÁS
        selected_rows = selection["selection"]["rows"] if selection else []

        if selected_rows:
            selected_row_index = selected_rows[0]
            selected_row = df_filtered.iloc[selected_row_index]
            selected_well = selected_row["well_position"]
            selected_flag = str(selected_row.get("flag", "")).strip()
            is_manual_review = selected_flag == "manuális értékelést igényel"
            is_validalhato = selected_well in validalhato_wells
            is_validated = selected_well in validated_wells

            # Validálás / visszavonás a kijelölt sorra
            col_val, col_unval, _ = st.columns([1, 1, 3])
            with col_val:
                if is_validalhato and not is_validated:
                    if st.button("✅ Sor validálása", width='stretch', type="primary"):
                        from datetime import datetime
                        now = datetime.now().strftime("%Y.%m.%d. %H:%M")
                        st.session_state["validated_wells"][selected_well] = now
                        st.session_state["full_results"] = None
                        st.rerun()
                elif is_validated:
                    st.success(f"✅ {validated_wells[selected_well]}")
                else:
                    st.warning("⚠️ Előbb döntsd el a flag-et")
            with col_unval:
                if is_validated:
                    if st.button("↩️ Visszavonás", width='stretch'):
                        del st.session_state["validated_wells"][selected_well]
                        st.session_state["full_results"] = None
                        st.rerun()

            st.divider()
            col_chart, col_edit = st.columns([2, 1])

            with col_chart:
                st.subheader(f"PCR görbe – Well: {selected_well}")
                try:
                    from app.output.samples_output import visual_samples
                    file_buf_viz = io.BytesIO(eds_bytes)
                    fig = visual_samples(
                        file=file_buf_viz,
                        sampleid_df=backend_layout,
                        selected_kit_name=kit_name,
                        well_position=selected_well
                    )
                    if fig:
                        st.plotly_chart(fig, width='stretch')
                except Exception as e:
                    st.error(f"Hiba a görbe betöltésekor: {e}")

            with col_edit:
                # --- "manuális értékelést igényel" sorok: Elfogad vagy Módosít ---
                if is_manual_review:
                    st.subheader("Ellenőrzés szükséges")
                    st.warning("Ez a sor manuális ellenőrzést igényel.")

                    action = st.radio(
                        "Döntés:",
                        options=["Elfogad", "Módosít"],
                        key=f"action_{selected_well}"
                    )

                    if action == "Elfogad":
                        if st.button("Elfogadás mentése", key=f"accept_{selected_well}", width='stretch'):
                            if selected_well not in st.session_state["accepted_wells"]: st.session_state["accepted_wells"].append(selected_well)
                            # override-ból töröljük ha volt korábbi módosítás
                            st.session_state["manual_overrides"].pop(selected_well, None)
                            st.session_state["full_results"] = None
                            st.success("Elfogadva!")
                            st.rerun()

                    else:  # Módosít
                        st.subheader("Eredmény módosítása")
                        render_modify_panel(selected_well, selected_row, overrides, kit_name)

                # --- Többi sor: módosítás + validálás visszavonása ---
                else:
                    st.subheader("Eredmény módosítása")
                    render_modify_panel(selected_well, selected_row, overrides, kit_name)



# ==============================
# Export
# ==============================
elif selected_view == "Export":
    st.header("Eredmények exportálása")

    eds_bytes = st.session_state.get("eds_bytes")
    final_layout = st.session_state.get("final_layout")
    kit_name = st.session_state.get("selected_kit")

    if eds_bytes is None or final_layout is None or kit_name is None:
        st.warning(
            "⚠️ Hiányzó adatok! Előbb töltsd fel az EDS fájlt, válassz PCR kitet, majd véglegesítsd a layoutot."
        )
    else:
        try:
            # Layout oszlopnevek kompatibilitása
            backend_layout = final_layout.copy()

            if "sample_id" in backend_layout.columns and "sampleid" not in backend_layout.columns:
                backend_layout["sampleid"] = backend_layout["sample_id"]
            elif "sampleid" in backend_layout.columns and "sample_id" not in backend_layout.columns:
                backend_layout["sample_id"] = backend_layout["sampleid"]

            file_buf = io.BytesIO(eds_bytes)

            # session_state-ből vesszük ha már kiszámolt, különben újraszámoljuk
            if st.session_state["full_results"] is not None:
                full_results = st.session_state["full_results"].copy()
            else:
                full_results = evaluate_samples(file_buf, backend_layout, kit_name)

            # Manuális módosítások alkalmazása az exporthoz is
            overrides = st.session_state.get("manual_overrides", {})
            accepted_wells = st.session_state.get("accepted_wells", set())

            for wp, changes in overrides.items():
                mask = full_results["well_position"] == wp
                for col, val in changes.items():
                    if col in full_results.columns:
                        full_results.loc[mask, col] = val
                # flag: "Manuálisan módosítva: {indok}"
                if "flag" in full_results.columns:
                    indok = changes.get("módosítás indoka", "")
                    full_results.loc[mask, "flag"] = f"Manuálisan módosítva: {indok}"

            # Elfogadott sorok flag frissítése
            for wp in accepted_wells:
                mask = full_results["well_position"] == wp
                if "flag" in full_results.columns:
                    full_results.loc[mask, "flag"] = "Elfogadva"

            # Validálás ideje oszlop – csak validált soroknál töltve
            validated_wells_export = st.session_state.get("validated_wells", {})
            full_results["Validálás ideje"] = full_results["well_position"].map(
                lambda wp: validated_wells_export.get(wp, "")
            )

            if full_results is None or full_results.empty:
                st.info("Nincs exportálható eredmény.")
                st.stop()

            # Elérhető oszlopok
            all_columns = list(full_results.columns)

            # Alapértelmezett oszlopok
            default_columns = [
                col for col in [
                    "well",
                    "well_position",
                    "sample_id",
                    "final_result",
                    "target",
                    "ct",
                    "valid",
                    "flag",
                    "Validálás ideje",
                    "well_type",
                ]
                if col in all_columns
            ]

            st.subheader("Export beállítások")

            selected_columns = st.multiselect(
                "Válaszd ki az exportálni kívánt oszlopokat:",
                options=all_columns,
                default=default_columns
            )

            file_format = st.radio(
                "Export formátum:",
                options=["csv", "txt", "xlsx"],
                horizontal=True
            )

            exclude_controls = st.checkbox(
                "Kontroll minták kizárása exportból",
                value=False
            )

            # Szűrés exporthoz / előnézethez
            export_df = full_results.copy()

            if exclude_controls:
                if "well_type" in export_df.columns:
                    export_df = export_df[export_df["well_type"] != "Control"].copy()
                elif "sample_id" in export_df.columns:
                    excluded_samples = {"NTC", "PTC", "Prep_NTC", "PrepNTC", "PK"}
                    export_df = export_df[~export_df["sample_id"].isin(excluded_samples)].copy()

            st.divider()
            st.subheader("Eredmények előnézete")

            if export_df.empty:
                st.warning("A szűrés után nincs megjeleníthető vagy exportálható adat.")
            elif selected_columns:
                preview_df = export_df[selected_columns].copy()
                st.dataframe(preview_df, width='stretch')

                file_data, file_name, mime = build_export_file(
                    df=export_df,
                    selected_columns=selected_columns,
                    file_format=file_format
                )

                st.download_button(
                    label=f"Eredmények letöltése ({file_format.upper()})",
                    data=file_data,
                    file_name=file_name,
                    mime=mime,
                    width='stretch'
                )
            else:
                st.info("Válassz ki legalább egy oszlopot az előnézethez és exporthoz.")

        except Exception as e:
            st.error(f"Hiba történt az export előkészítése során: {e}")