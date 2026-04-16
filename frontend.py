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
        "",
        INPUT_OPTIONS,
        index=INPUT_OPTIONS.index(st.session_state["input"])
        if st.session_state["input"] in INPUT_OPTIONS else None,
        key="input",
        on_change=on_input_change
    )

with st.sidebar.expander("Eredmények", expanded=True):
    st.radio(
        "",
        RESULT_OPTIONS,
        index=RESULT_OPTIONS.index(st.session_state["results"])
        if st.session_state["results"] in RESULT_OPTIONS else None,
        key="results",
        on_change=on_results_change
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
        key="eds_uploader"
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
            st.session_state["eds_uploader"] = None            
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
        st.dataframe(df.head(200), use_container_width=True)

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

    # --------------------------------------------------
    # Mód kiválasztása
    # --------------------------------------------------
    sample_id_mode = st.radio(
        "Mintaazonosítók megadásának módja",
        [
            "Általános mintaazonosítók használata",
            "Excel sablon feltöltése"
        ],
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
            key="sample_id_excel_uploader"
        )

        if uploaded_sample_file is not None:
            if st.button("Feltöltött Excel beolvasása", use_container_width=True):
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
        use_container_width=True,
        num_rows="fixed",
        key="sample_id_plate_editor"
        )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Grid módosítások mentése", use_container_width=True):
            try:
                updated_sample_id_df = grid_to_sample_id_df(edited_grid)
                st.session_state["sample_id_df"] = updated_sample_id_df
                st.success("A mintaazonosítók frissítése sikeresen mentve.")
                st.rerun()
            except Exception as e:
                st.error(f"A grid mentése nem sikerült: {e}")

    with col2:
        if st.button("Grid kiürítése", use_container_width=True):
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
            # Ez a selectbox adja meg a változó értékét!
            selected_type = st.selectbox(
                "Melyik kontrollt helyezed el?", 
                options=final_control_options
            )
        with col2:
            # Csak az EDS-ben lévő welleket adjuk fel (ha be van töltve)
            raw_df = st.session_state.get("raw_df")
        

            if raw_df is not None:
                # Kivesszük az egyedi well-neveket és sorba rendezzük őket
                # Fontos a logikus sorrend (A1, A2... nem A1, A10, A2)
                available_wells = sorted(
                raw_df['well_position'].unique(), 
                key=lambda x: (ord(x[0]), int(x[1:]))
                )
                st.success(f"Az EDS fájl alapján {len(available_wells)} mért well közül választhatsz.")
            else:
        # Ha nincs EDS, vagy minden well-t felajánlasz, vagy (ajánlott) korlátozod
                available_wells = []
                st.warning("⚠️ Nincs betöltött EDS fájl! Kérlek, előbb töltsd fel a futási fájlt a 'Futási file' menüpontban.")

        # 2. A multiselect már csak ezeket mutatja
            if available_wells:
                selected_wells = st.multiselect(
                    f"Wells a(z) {selected_type} kontrollhoz",
                    options=available_wells,
                    key=f"wells_input_{selected_type}"
                )
            else:
                st.info("A kontrollok kijelöléséhez szükség van a betöltött futási adatokra.")

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
        
        if st.button("ADATOK VÉGLEGESÍTÉSE ÉS ELEMZÉS INDÍTÁSA", type="primary", use_container_width=True):
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

    # Adatok lekérése a session_state-ből
    eds_bytes = st.session_state.get("eds_bytes")
    final_layout = st.session_state.get("final_layout")
    kit_name = st.session_state.get("selected_kit")

    if eds_bytes is None or final_layout is None or kit_name is None:
        st.warning("⚠️ Hiányzó adatok! Kérlek, előbb töltsd fel az EDS fájlt és véglegesítsd a layoutot az 'Összefoglaló' fülön.")
    else:
        try:
            # 1. Kontroll táblázat generálása (ez kell a visual_PCR_curves_controls-nak)
            file_for_backend = io.BytesIO(eds_bytes)
            df_controls_result = control_table(
                file=file_for_backend, 
                sampleid_df=final_layout, 
                selected_kit_name=kit_name
            )

            # --- TÁBLÁZAT MEGJELENÍTÉSE ---
            st.subheader("Kontroll statisztika")
            if df_controls_result is not None and not df_controls_result.empty:
                st.dataframe(df_controls_result, use_container_width=True)
                
                st.divider()

                # --- GÖRBÉK MEGJELENÍTÉSE ---
                st.subheader("Kontroll amplifikációs görbék")

                # Kigyűjtjük az egyedi kontroll neveket a táblázatból
                available_control_names = df_controls_result["sample_id"].unique()

                selected_control = st.selectbox(
                    "Válassz egy kontrollt a görbe megtekintéséhez:",
                    options=available_control_names
                )

                if selected_control:
                
                # Meghívjuk a saját vizualizációs függvényedet a kért paraméterekkel
                    file_for_viz = io.BytesIO(eds_bytes)
                    fig_controls = visual_PCR_curves_controls(
                        file=file_for_viz,
                        sampleid_df=final_layout,
                        selected_kit_name=kit_name,
                        controls_table=df_controls_result,
                        control_name=selected_control
                    )

                # Megjelenítés (attól függően, hogy a függvényed Plotly vagy Matplotlib objektumot ad vissza)
                    if fig_controls is not None:
                    # Ha Plotly (px/go)
                        st.plotly_chart(fig_controls, use_container_width=True)
                    # Ha a függvényed Matplotlib/Seaborn (plt.figure), használd ezt:
                        #st.pyplot(fig_controls)
                    else:
                        st.info("A vizualizáció nem elérhető.")
            else:
                st.info("Nincsenek megjeleníthető kontroll adatok.")

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
            
            # Eredmények kiszámítása
            full_results = evaluate_samples(file_buf, backend_layout, kit_name)
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
            
                fig_grid.update_traces(marker=dict(size=22, symbol="square", line=dict(width=1, color="black")))
            
                fig_grid.update_layout(
                    clickmode='event+select',
                    xaxis=dict(side='top', type='category', title=""),
                # Itt a titok: Fix kategória sorrend + fordított skála az A felülhöz
                    yaxis=dict(type='category', title="", categoryorder='array', categoryarray=rows, autorange="reversed"),
                    showlegend=True, height=550, margin=dict(l=0, r=0, b=0, t=40)
                )

                # Kattintás figyelése
                # FONTOS: Nem használunk manuális st.rerun()-t a blokkon belül!
                event = st.plotly_chart(fig_grid, on_select="rerun", use_container_width=True, key="plate_chart")

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
                            st.plotly_chart(fig_s, use_container_width=True)
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
                    st.plotly_chart(fig_all, use_container_width=True)


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
            
            # Oszlopnév kompatibilitás
            backend_layout = final_layout.copy()
            if 'sample_id' in backend_layout.columns and 'sampleid' not in backend_layout.columns:
                backend_layout['sampleid'] = backend_layout['sample_id']
            elif 'sampleid' in backend_layout.columns and 'sample_id' not in backend_layout.columns:
                backend_layout['sample_id'] = backend_layout['sampleid']

            full_results = evaluate_samples(file_buf, backend_layout, kit_name)
            
            # Csak a fontos oszlopokat mutatjuk meg az átláthatóságért
            display_cols = ['well', 'well_position', 'sample_id','final_result', 'target', 'ct' ]
            # Ellenőrizzük, hogy minden kért oszlop létezik-e
            existing_cols = [c for c in display_cols if c in full_results.columns]
            df_display = full_results[existing_cols]

        except Exception as e:
            st.error(f"Hiba az adatok feldolgozása során: {e}")
            st.stop()

        # 2. TÁBLÁZAT MEGJELENÍTÉSE KIJELÖLHETŐ SOROKKAL
        st.write("Kattints egy sorra a PCR görbe megtekintéséhez:")
        
        # A táblázat, ahol a sor kijelölése váltja ki a görbe megjelenítését
        selection = st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun", # Ez teszi interaktívvá
            selection_mode="single-row" # Egyszerre egy görbét nézünk
        )

        # 3. GÖRBE MEGJELENÍTÉSE A TÁBLÁZAT ALATT (VAGY MELLETT)
        # Ha a felhasználó kijelölt egy sort a táblázatban
        if selection and selection["selection"]["rows"]:
            selected_row_index = selection["selection"]["rows"][0]
            selected_well = df_display.iloc[selected_row_index]["well_position"]
            
            st.divider()
            with st.container(border=True):
                st.subheader(f" PCR Görbe – Well: {selected_well}")
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
                        st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Hiba a görbe betöltésekor: {e}")
        else:
            st.info("Jelölj ki egy sort a táblázatban a részletes PCR görbe megjelenítéséhez.")

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
            full_results = evaluate_samples(file_buf, backend_layout, kit_name)

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
                st.dataframe(preview_df, use_container_width=True)

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
                    use_container_width=True
                )
            else:
                st.info("Válassz ki legalább egy oszlopot az előnézethez és exporthoz.")

        except Exception as e:
            st.error(f"Hiba történt az export előkészítése során: {e}")
