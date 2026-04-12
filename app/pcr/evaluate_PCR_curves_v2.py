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

    if window % 2 == 0: window += 1

    results = []
    df = mapping_sampleid(file, csv_path)
    channels = load_selected_kit(selected_kit_name)[2]

    abs_min_derivative_map = {
        "FAM": 8000, "VIC": 2500, "ABY": 3000, "Cy5": 3000, "ROX": 8000 
    } # Cy5-öt kicsit emeltem a biztonság kedvéért

    for (well, well_position, sid), df_sample in df.groupby([well_col, well_position_col, sample_id]):
        row_result = {"well": well, "well_position": well_position, 'sample_id': sid}
        
        # ELŐSZŰRÉS: Keressünk globális ugrást (technikai hiba)
        # Ha több csatorna dy_max-a ugyanoda esik a 1-12 ciklus között
        peak_cycles = {}
        
        # Először kiszámoljuk minden csatornára a deriváltat
        channel_data = {}
        for ch in channels:
            if ch not in df_sample.columns: continue
            y = df_sample[ch].astype(float).values
            y_smooth = savgol_filter(y, window, poly)
            dy = savgol_filter(y_smooth, window, poly, deriv=1)
            channel_data[ch] = {"dy": dy, "y": y_smooth}
            peak_cycles[ch] = np.argmax(dy)

        # Globális hiba detektálása: ha legalább 3 csatorna egyszerre ugrik az elején
        early_peaks = [c for ch, c in peak_cycles.items() if 1 <= c <= 12]
        is_global_artifact = len(early_peaks) >= 3 # és ezek közel vannak egymáshoz

        for ch in channels:
            if ch not in channel_data:
                row_result[ch] = np.nan
                continue

            dy = channel_data[ch]["dy"]
            y_smooth = channel_data[ch]["y"]
            x = df_sample[cycle_col].values
            
            dy_max = dy.max()
            abs_min = abs_min_derivative_map.get(ch, 3000)

            # 1. KÜSZÖB ELLENŐRZÉS
            if dy_max < abs_min:
                row_result[ch] = "negatív"
                continue

            # 2. GLOBÁLIS ARTIFAKT SZŰRÉS
            # Ha globális hibát észleltünk és ez a csatorna is ott peakel
            if is_global_artifact and 1 <= peak_cycles[ch] <= 12:
                row_result[ch] = "negatív (technikai hiba)"
                continue

            # 3. SUSTAINED RISE (Tartós emelkedés ellenőrzése)
            # A deriváltnak legalább 3 egymást követő ciklusban a küszöb felett kell lennie
            high_dy = dy > (abs_min * 0.4) # egy enyhébb küszöb a folytonossághoz
            consecutive_rise = False
            for i in range(len(high_dy)-3):
                if all(high_dy[i:i+3]):
                    consecutive_rise = True
                    break
            
            if not consecutive_rise:
                row_result[ch] = "negatív (zaj)"
                continue

            # 4. CT MEGHATÁROZÁS (2. derivált)
            d2y = savgol_filter(y_smooth, window, poly, deriv=2)
            
            # Csak a 12. ciklus után és ahol pozitív a meredekség
            mask = (dy > 0) & (x > 12) 
            
            if not np.any(mask):
                row_result[ch] = "negatív"
                continue

            valid_d2 = d2y[mask]
            valid_x = x[mask]
            
            ct_idx_local = np.argmax(valid_d2)
            row_result[ch] = float(valid_x[ct_idx_local])

        results.append(row_result)

    # ... (maradék feldolgozás)
    results_df = pd.DataFrame(results)

    evaluate_PCR_curves_result = results_df.melt(
        id_vars=["well", "well_position", 'sample_id'],
        var_name="dye",
        value_name="Result"
    )

    evaluate_PCR_curves_result = evaluate_PCR_curves_result.sort_values(by="well").reset_index(drop=True)

    return evaluate_PCR_curves_result