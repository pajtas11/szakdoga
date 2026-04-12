from datetime import datetime
import io
import pandas as pd


def build_export_file(df: pd.DataFrame, selected_columns: list[str], file_format: str):
    """
    A kiválasztott oszlopokból exportálható fájl készítése memóriában.
    Visszatér:
        - file_bytes vagy string
        - file_name
        - mime_type
    """
    if df is None or df.empty:
        raise ValueError("Nincs exportálható adat.")

    if not selected_columns:
        raise ValueError("Legalább egy oszlopot ki kell választani exporthoz.")

    missing_cols = [col for col in selected_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Hiányzó oszlop(ok): {missing_cols}")

    export_df = df[selected_columns].copy()

    date_str = datetime.today().strftime("%Y%m%d_%H%M%S")
    base_filename = f"pcr_results_{date_str}"
    file_format = file_format.lower().strip()

    if file_format == "csv":
        data = export_df.to_csv(index=False, sep=";", encoding="utf-8")
        return data, f"{base_filename}.csv", "text/csv"

    elif file_format == "txt":
        data = export_df.to_csv(index=False, sep="\t", encoding="utf-8")
        return data, f"{base_filename}.txt", "text/plain"

    elif file_format == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="PCR_results")
        output.seek(0)
        return (
            output.getvalue(),
            f"{base_filename}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    else:
        raise ValueError(f"Nem támogatott fájlformátum: {file_format}")