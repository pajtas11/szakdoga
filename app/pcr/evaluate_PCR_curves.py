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
        sample_id = "sample_id",
        cycle_col="cycle",
        window=9,
        poly=2):
    
    results = []
    df = mapping_sampleid(file, sampleid_df)
    df_final = df[df[cycle_col] > 10]
    channels = load_selected_kit(selected_kit_name)[2]
    x = df_final[cycle_col].values

    # Alapmeredekség beállítása csatornánként
    abs_min_derivative_map = {
        "FAM": 5000, "VIC": 2500, "ABY": 3000, "Cy5": 3000, "ROX": 4000 } 

    # c
    for (well, well_position, sid), df_sample in df_final.groupby([well_col, well_position_col, sample_id]):
        row_result = {"well": well, "well_position": well_position, 'sample_id': sid}
        
        for ch in channels:
            if ch not in df_sample.columns: continue
            y = df_sample[ch].astype(float).values
            y_smooth = savgol_filter(y, window, poly)
            dy = savgol_filter(y_smooth, window, poly, deriv=1)
            x = df_final['cycle'].values
            dy_max = dy.max()
            abs_min = abs_min_derivative_map.get(ch, 3000)

            if dy_max < abs_min:
                row_result[ch] = "negatív"
                continue
    
            else: 
                d2y = savgol_filter(y_smooth, window, poly, deriv=2)
                mask = (dy > 0)
            
                if not np.any(mask):
                    row_result[ch] = "negatív"
                    continue

                valid_d2 = d2y[mask]
            
                ct_idx_local = np.argmax(valid_d2)
                row_result[ch] = float(x[ct_idx_local])

        results.append(row_result)

    results_df = pd.DataFrame(results)
    evaluate_PCR_curves_result = results_df.melt(
        id_vars=["well", "well_position", 'sample_id'],
        var_name="dye",
        value_name="Result")

    evaluate_PCR_curves_result = evaluate_PCR_curves_result.sort_values(by="well").reset_index(drop=True)

    return evaluate_PCR_curves_result