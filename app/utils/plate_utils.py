import pandas as pd
import streamlit as st
from pathlib import Path

ROWS_384 = list("ABCDEFGHIJKLMNOP")
COLS_384 = list(range(1, 25))


def create_empty_plate_grid() -> pd.DataFrame:
    grid = pd.DataFrame(
        "",
        index=ROWS_384,
        columns=[str(c) for c in COLS_384]
    )
    grid.index.name = "Sor"
    return grid


def normalize_sample_id_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # oszlopnevek normalizálása
    normalized_columns = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if c == "well":
            normalized_columns[col] = "Well"
        elif c in ["well_position", "well position", "position"]:
            normalized_columns[col] = "Well_position"
        elif c in ["sample_id", "sampleid", "sample"]:
            normalized_columns[col] = "Sample_ID"

    df = df.rename(columns=normalized_columns)

    if "Sample_ID" not in df.columns:
        raise ValueError(f"Hiányzik a Sample_ID oszlop. Meglévő oszlopok: {list(df.columns)}")

    # Elsődlegesen a Well_position-t használjuk, ha nincs, akkor a Well-t
    if "Well_position" in df.columns:
        df["Well_final"] = df["Well_position"]
    elif "Well" in df.columns:
        df["Well_final"] = df["Well"]
    else:
        raise ValueError(f"Hiányzik a Well_position és a Well oszlop is. Meglévő oszlopok: {list(df.columns)}")

    df["Well_final"] = (
        df["Well_final"]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    df["Sample_ID"] = df["Sample_ID"].fillna("").astype(str).str.strip()

    return df[["Well_final", "Sample_ID"]].rename(columns={"Well_final": "Well"})


def sample_id_df_to_grid(sample_id_df: pd.DataFrame) -> pd.DataFrame:
    grid = create_empty_plate_grid()

    if sample_id_df is None or sample_id_df.empty:
        return grid

    df = normalize_sample_id_df(sample_id_df)

    valid_wells = {f"{r}{c}" for r in ROWS_384 for c in COLS_384}

    for _, row in df.iterrows():
        well = row["Well"]
        sample_id = row["Sample_ID"]

        if well in valid_wells:
            row_letter = well[0]
            col_number = well[1:]
            grid.loc[row_letter, col_number] = sample_id

    return grid


def grid_to_sample_id_df(grid_df: pd.DataFrame) -> pd.DataFrame:
    records = []

    for row_letter in ROWS_384:
        for col_number in COLS_384:
            value = grid_df.loc[row_letter, str(col_number)]
            if pd.isna(value):
                value = ""

            records.append({
                "Well_position": f"{row_letter}{col_number}",
                "Sample_ID": str(value).strip()
            })

    return pd.DataFrame(records)


def clear_sample_id_state():
    st.session_state["sample_id_source_path"] = None
    st.session_state["sample_id_file_name"] = None
    st.session_state["sample_id_df"] = None
    st.session_state["plate_layout_df"] = None
    st.session_state["sample_id_mode"] = None
    if "sample_id_excel_uploader" in st.session_state:
        st.session_state["sample_id_excel_uploader"] = None


def load_basic_sample_ids():
    basic_sampleid_path = Path("app/templates/basic_sampleid.csv")

    if not basic_sampleid_path.exists():
        st.error(f"A fájl nem található: {basic_sampleid_path}")
        return

    try:
        df_basic = pd.read_csv(basic_sampleid_path, delimiter=";")

        st.session_state["sample_id_source_path"] = str(basic_sampleid_path)
        st.session_state["sample_id_file_name"] = basic_sampleid_path.name
        st.session_state["sample_id_df"] = df_basic
        st.session_state["plate_layout_df"] = None

        st.success(f"Általános mintaazonosítók betöltve: {basic_sampleid_path.name}")

    except Exception as e:
        st.error(f"A fájl beolvasása nem sikerült: {e}")

def load_excel_sample_ids(uploaded_file):
    try:
        xls = pd.ExcelFile(uploaded_file)

        required_sheets = ["384well_plate", "Sample_ID"]
        missing_sheets = [sheet for sheet in required_sheets if sheet not in xls.sheet_names]

        if missing_sheets:
            st.error(
                f"A feltöltött Excel nem megfelelő. Hiányzó munkalap(ok): {', '.join(missing_sheets)}"
            )
            return

        plate_df = pd.read_excel(xls, sheet_name="384well_plate")
        sample_id_df = pd.read_excel(xls, sheet_name="Sample_ID")

        st.session_state["sample_id_source_path"] = uploaded_file.name
        st.session_state["sample_id_file_name"] = uploaded_file.name
        st.session_state["plate_layout_df"] = plate_df
        st.session_state["sample_id_df"] = sample_id_df

        st.success(f"Excel sablon sikeresen betöltve: {uploaded_file.name}")

    except Exception as e:
        st.error(f"A fájl beolvasása nem sikerült: {e}")