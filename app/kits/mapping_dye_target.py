#import other functions
from app.kits.selected_kit import load_selected_kit
from app.pcr.evaluate_PCR_curves import evaluate_PCR_curves


def mapping_dye_target(file, 
        csv_path,
        selected_kit_name, 
        well_col="well",
        well_position_col="well_position",
        sample_id = "sample_id",
        cycle_col="cycle",
        window=9,
        poly=2):
    
    # kit 
    target_dye_map= load_selected_kit(selected_kit_name)[1]

    #mapping
    pcr_result = evaluate_PCR_curves(file, 
        csv_path,
        selected_kit_name, 
        well_col="well",
        well_position_col="well_position",
        sample_id = "sample_id",
        cycle_col="cycle",
        window=9,
        poly=2)

    pcr_result['Target'] = pcr_result['dye'].map(target_dye_map)

    return pcr_result

