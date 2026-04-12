#import libraries
import pandas as pd
import numpy as np
from scipy.signal import savgol_filter

# import other functions
from app.pcr.sampleid_mapping import mapping_sampleid
from app.kits.selected_kit import load_selected_kit


def evaluate_PCR_curves(
        file, 
        csv_path,
        selected_kit_name, 
        well_col="well",
        well_position_col="well_position",
        sample_id = "sample_id",
        cycle_col="cycle",
        window=9,
        poly=2):

    #Savitzky–Golay szűrő csak páratlan window-t fogad el, ezért ha páros, növeli eggyel.
    if window % 2 == 0:
        window += 1

    results = []
    df = mapping_sampleid(file, csv_path)
    channels = load_selected_kit(selected_kit_name)[2]

    #Well-enként feldolgozás
    for (well, well_position, sample_id), df_sample in df.groupby([well_col, well_position_col, sample_id]):

        row_result = {
            "well": well,
            "well_position": well_position,
            'sample_id' : sample_id
        }

        for ch in channels:

            if ch not in df_sample.columns:
                row_result[ch] = np.nan
                continue

            y = df_sample[ch].astype(float).values
            x = df_sample[cycle_col].values

            if len(y) < window + 2:
                row_result[ch] = np.nan
                continue

            try:
                y_smooth = savgol_filter(y, window_length=window, polyorder=poly)
            except ValueError:
                row_result[ch] = np.nan
                continue

            # ===== 1. DERIVÁLT (emelkedési sebesség) ===== 
            dy = savgol_filter(
                y_smooth,
                window_length=window,
                polyorder=poly,
                deriv=1
            )

            #legnagyobb meredekség meghatározása
            dy_max = dy.max()

            #Csatorna-specifikus küszöb
            abs_min_derivative_map = {
                "FAM": 8000,
                "VIC": 2500,
                "ABY": 3000,
                "Cy5": 1500,
                "ROX": 8000
            }

            abs_min_derivative = abs_min_derivative_map.get(ch, 3000)

            # Negatív minta szűrés
            if dy_max < abs_min_derivative:
                row_result[ch] = "negatív"
                continue

            # ===== 2. DERIVÁLT =====
            d2y = savgol_filter(
                y_smooth,
                window_length=window,
                polyorder=poly,
                deriv=2
            )

            # ===== MASZK: csak növekvő szakaszon keresünk Ct-t=====
            mask = dy > 0

            # kizárjuk az első pár ciklust (baseline biztonság)
            min_cycle = 10
            mask = mask & (x > min_cycle)

            if not np.any(mask):
                row_result[ch] = "negatív"
                continue

            valid_d2 = d2y[mask]
            valid_x = x[mask]

            ct_idx_local = np.argmax(valid_d2)
            ct_value = float(valid_x[ct_idx_local])

            row_result[ch] = ct_value

        results.append(row_result)

    results_df = pd.DataFrame(results)

    evaluate_PCR_curves_result = results_df.melt(
        id_vars=["well", "well_position", 'sample_id'],
        var_name="dye",
        value_name="Result"
    )

    evaluate_PCR_curves_result = evaluate_PCR_curves_result.sort_values(by="well").reset_index(drop=True)

    return evaluate_PCR_curves_result
