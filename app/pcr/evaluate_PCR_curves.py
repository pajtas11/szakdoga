#import libraries
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter
 
# import other functions
from app.pcr.sampleid_mapping import mapping_sampleid
from app.kits.selected_kit import load_selected_kit
 
 
def evaluate_PCR_curves(
        file, 
        sampleid_df,
        selected_kit_name, 
        well_col="well",
        well_position_col="well_position",
        sample_id="sample_id",
        cycle_col="cycle",
        dy_mean_threshold=1000,
        borderline_range=(900, 1100),
        window=9,
        poly=2):
    
    results = []
    df = mapping_sampleid(file, sampleid_df)
    df_final = df[df[cycle_col] > 10]
    channels = load_selected_kit(selected_kit_name)[2]
    low, high = borderline_range
 
    for (well, well_position, sid), df_sample in df_final.groupby([well_col, well_position_col, sample_id]):
        row_result = {"well": well, "well_position": well_position, "sample_id": sid}
        x = df_sample[cycle_col].values
 
        for ch in channels:
            if ch not in df_sample.columns:
                continue
 
            y = df_sample[ch].astype(float).values
            y_smooth = savgol_filter(y, window, poly)
            dy = savgol_filter(y_smooth, window, poly, deriv=1)
            dy_mean = dy.mean()
 
            row_result[ch] = "negatív" if dy_mean <= dy_mean_threshold else None
            row_result[f"{ch}_flag"] = bool(low <= dy_mean <= high)
 
            if dy_mean <= dy_mean_threshold:
                continue
 
            # --- Ct meghatározás: SDM (Second Derivative Maximum) ---
            d2y = savgol_filter(y_smooth, window, poly, deriv=2)
            mask = (dy > 0)
 
            if not np.any(mask):
                row_result[ch] = "negatív"
                continue
 
            valid_d2 = d2y[mask]
            x_masked = x[mask]
            ct_idx = np.argmax(valid_d2)
            row_result[ch] = float(x_masked[ct_idx])
 
        results.append(row_result)
 
    results_df = pd.DataFrame(results)
 
    # --- Result oszlopok melt-je ---
    evaluate_PCR_curves_result = results_df.melt(
        id_vars=["well", "well_position", "sample_id"] + [f"{ch}_flag" for ch in channels if ch in results_df.columns],
        value_vars=[ch for ch in channels if ch in results_df.columns],
        var_name="dye",
        value_name="Result")
 
    # --- Flag oszlop a megfelelő csatornához rendelve ---
    evaluate_PCR_curves_result["flag"] = evaluate_PCR_curves_result.apply(
        lambda row: row.get(f"{row['dye']}_flag", False), axis=1
    )
 
    # --- Felesleges flag oszlopok eltávolítása ---
    drop_cols = [f"{ch}_flag" for ch in channels if f"{ch}_flag" in evaluate_PCR_curves_result.columns]
    evaluate_PCR_curves_result = evaluate_PCR_curves_result.drop(columns=drop_cols)
 
    evaluate_PCR_curves_result = evaluate_PCR_curves_result.sort_values(by="well").reset_index(drop=True)
 
    return evaluate_PCR_curves_result