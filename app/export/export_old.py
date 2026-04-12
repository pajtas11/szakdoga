#import libraries
from pathlib import Path
from datetime import datetime
import pandas as pd
import openpyxl

from pcr.evaluate_samples import evaluate_samples

def export_pcr_results(file_format,
                        file, 
                        csv_path,
                        selected_kit_name, 
                        well_col="well",
                        well_position_col="well_position",
                        sample_id = "sample_id",
                        cycle_col="cycle",
                        window=9,
                        poly=2):

    interpret_pcr_results = evaluate_samples(file, 
                        csv_path,
                        selected_kit_name, 
                        well_col="well",
                        well_position_col="well_position",
                        sample_id = "sample_id",
                        cycle_col="cycle",
                        window=9,
                        poly=2)
    
    # --- ellenőrzés a szükséges oszlopokra ---
    required_cols = ["SampleID", "valid", "final_result"]
    missing = [c for c in required_cols if c not in interpret_pcr_results.columns]
    if missing:
        raise ValueError(f"Hiányzó oszlop(ok) az exporthoz: {missing}")


    # --- kontrollminták kizárása ---
    excluded_samples = {"NTC", "PK", "PrepNTC"}

    export_df = (
        interpret_pcr_results[required_cols]
        .loc[~interpret_pcr_results["SampleID"].isin(excluded_samples)]
        .copy()
    )

    if export_df.empty:
        raise ValueError("Nincs exportálható minta (csak kontrollminták találhatók).")


    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_filename = "pcr_results"

    file_format = file_format.lower().strip()
    if file_format not in {"csv", "xlsx", "txt"}:
        raise ValueError(f"Nem támogatott fájlformátum: {file_format}")

    date_str = datetime.today().strftime("%Y%m%d")

    counter = 1
    while True:
        filename = f"{date_str}_{base_filename}_{counter:03d}.{file_format}"
        output_path = output_dir / filename
        if not output_path.exists():
            break
        counter += 1

    if file_format == "csv":
        export_df.to_csv(output_path, sep=";", index=False, encoding="utf-8")

    elif file_format == "xlsx":
        export_df.to_excel(output_path, index=False)

    elif file_format == "txt":
        export_df.to_csv(output_path, sep="\t", index=False, encoding="utf-8")

    return output_path



