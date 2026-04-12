#import libraries
import plotly.express as px

#import other functions
from app.pcr.evaluate_samples import evaluate_samples
from app.pcr.sampleid_mapping import mapping_sampleid
from app.kits.selected_kit import load_selected_kit



def control_table (file, 
                sampleid_df,
                selected_kit_name, 
                well_col="well",
                well_position_col="well_position",
                sample_id = "sample_id",
                cycle_col="cycle",
                window=9,
                poly=2):
    
    final_results = evaluate_samples (file, 
                sampleid_df,
                selected_kit_name, 
                well_col="well",
                well_position_col="well_position",
                sample_id = "sample_id",
                cycle_col="cycle",
                window=9,
                poly=2) 
    kontroll = final_results[(final_results['sample_id'] == 'NTC')|(final_results['sample_id'] == 'Prep_NTC')|(final_results['sample_id'] == 'PK')]
    controls_table= kontroll[['well', 'well_position', 'sample_id', 'valid', 'final_result']].reset_index(drop=True)
    return controls_table


def visual_PCR_curves_controls(file, sampleid_df, selected_kit_name, controls_table, control_name):

    signals = mapping_sampleid(file, sampleid_df)

    # Kontroll sor kiválasztása
    control_row = controls_table[
        controls_table["sample_id"] == control_name
    ]

    if control_row.empty:
        print(f"Nincs ilyen kontroll: {control_name}")
        return

    well_pos = control_row["well_position"].iloc[0]

    well_pos_signal = signals[
        signals["well_position"] == well_pos
    ]

    target_dye_map = load_selected_kit(selected_kit_name)[1]
    channels = load_selected_kit(selected_kit_name)[2]
    selected_kit = load_selected_kit(selected_kit_name)[0]

    control_rules = selected_kit.get("controls", {}).get(control_name, {}).get("rules", {})

# target → dye mapping
    dye_by_target = {v: k for k, v in target_dye_map.items()}

    if control_rules:
        rule_text_parts = []

        for target_name, expected_negative in control_rules.items():

            dye = dye_by_target.get(target_name, "UNKNOWN")

            status = "negatív" if expected_negative else "pozitív"

            rule_text_parts.append(f"{target_name} ({dye}) = {status}")

        rule_text = "Valid: " + ",  ".join(rule_text_parts)

    else:
        rule_text = ""

# -------------------
# Cím összeállítása
# -------------------

    title_text = f"{control_name} – {well_pos} well"

    if rule_text:
        title_text += "<br>" + rule_text

    fig = px.line(
        well_pos_signal,
        x="cycle",
        y=channels,
        title=title_text
    )

    return fig

