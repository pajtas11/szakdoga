import plotly.express as px
from app.kits.mapping_dye_target import mapping_dye_target
from app.pcr.sampleid_mapping import mapping_sampleid
from app.kits.selected_kit import load_selected_kit

def build_colored_legend(df_sample, color_map):

    legend_parts = []

    for _, row in df_sample.iterrows():
        target = row["Target"]
        dye = row["dye"]
        result = row["Result"]

        # Szín lekérése a festék alapján
        color = color_map.get(dye, "black")

        if isinstance(result, (int, float)):
            text = f"{target} ({dye}): pozitív (Ct: {result:.1f})"
        else:
            text = f"{target} ({dye}): {result}"

        # Színezett HTML
        colored_text = f"<span style='color:{color}'>{text}</span>"

        legend_parts.append(colored_text)

    return ", ".join(legend_parts)



def visual_samples(file, sampleid_df, selected_kit_name, well_position):
    signals = mapping_sampleid(file, sampleid_df)
    well_pos_signal = signals[
        signals["well_position"] == well_position
    ]
    sample_id = signals[signals['well_position'] == well_position]['sample_id'].min()
    
    pcr_result = mapping_dye_target(file, 
        sampleid_df,
        selected_kit_name, 
        well_col="well",
        well_position_col="well_position",
        sample_id = "sample_id",
        cycle_col="cycle",
        window=9,
        poly=2)

    sample_result = pcr_result[pcr_result['well_position'] == well_position]
    channels = load_selected_kit(selected_kit_name)[2]

    color_map = {
        "FAM": "#3a86ff",
        "VIC": "#8338ec",
        "ABY": "#2a9d8f",
        "CY5": "#fb5607", 
        "ROX": "#ffbe0b"}
    
    title_text = f"{well_position} – {sample_id}"
    result_text = build_colored_legend(sample_result, color_map)

    
    if result_text:
        title_text += "<br>" + result_text

    fig = px.line(
    well_pos_signal,
    x="cycle",
    y=channels,
    title = title_text,
    color_discrete_map=color_map
    )

    return fig


