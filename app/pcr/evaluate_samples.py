# import libraries
import pandas as pd

### Import other functions
from app.kits.mapping_dye_target import mapping_dye_target
from app.kits.selected_kit import load_selected_kit


def evaluate_samples(file, 
                        sampleid_df,
                        selected_kit_name, 
                        well_col="well",
                        well_position_col="well_position",
                        sample_id = "sample_id",
                        cycle_col="cycle",
                        window=9,
                        poly=2): 
    
    pcr_result = mapping_dye_target(file, 
                                    sampleid_df,
                                    selected_kit_name, 
                                    well_col="well",
                                    well_position_col="well_position",
                                    sample_id = "sample_id",
                                    cycle_col="cycle",
                                    window=9,
                                    poly=2)
    
    selected_kit = load_selected_kit(selected_kit_name)[0]

    def is_negative(v):
        if pd.isnull(v):
            return False
        s = str(v).strip().lower()
        return s.startswith('negat')

    def is_numeric(v):
        return pd.notnull(pd.to_numeric(v, errors='coerce'))

    final_rows = []
    group_cols = ['well', 'well_position', 'sample_id']

    controls = selected_kit["controls"]
    internal_control = selected_kit.get("internal_control_name", "IC")


    for (well, well_pos, sample_id), g in pcr_result.groupby(group_cols):

        by_target = g.set_index('Target')['Result'].to_dict()
        targets = list(by_target.keys())

        has_ic = 'IC' in targets

        neg_flags = {t: is_negative(by_target[t]) for t in targets}
        num_flags = {t: is_numeric(by_target[t]) for t in targets}


        valid = False
        final_result = ""
        target = ""
        ct = ""

        # -------------------
        # NTC
        # -------------------

        if sample_id == 'NTC':
            if controls['NTC']['rules'] == neg_flags:
                valid = True
                final_result = 'Valid NTC'
            else:
                valid = False
                final_result = 'Invalid NTC'

        # -------------------
        # PK
        # -------------------


        elif sample_id == 'PK':
            if controls['PK']['rules'] == neg_flags:
                valid = True
                final_result = 'Valid PK'
            else:
                valid = False
                final_result = 'Invalid PK'
    
        # -------------------
        # PrepNTC
        # -------------------

        elif sample_id == 'Prep_NTC':
            other_targets = [t for t in targets if t !=  'IC']

            if has_ic:
                ic_numeric = num_flags.get('IC', True)

                others_negative = all(
                    neg_flags.get(t, True) for t in other_targets
                ) if other_targets else True

                if ic_numeric and others_negative:
                    valid = True
                    final_result = 'Valid PrepNTC'
                else:
                    valid = False
                    final_result = 'Invalid PrepNTC'
            else:
            # nincs IC → minden targetnek negatívnak kell lennie
                if all(neg_flags.get(t, False) for t in targets):
                    valid = True
                    final_result = 'Valid PrepNTC (IC nélkül)'
                else:
                    valid = False
                    final_result = 'Invalid PrepNTC'

        # -------------------
        # ISMERETLEN MINTÁK
        # -------------------

        else:
            positive_targets = [t for t in targets if num_flags.get(t, False)]
            positive_non_ic = [t for t in positive_targets if t != 'IC']

            if has_ic:
                ic_positive = num_flags.get('IC', False)

                if not positive_non_ic and ic_positive:
                    valid = True
                    final_result = 'negatív'

                elif positive_non_ic:
                    valid = True
                    final_result = 'pozitív'
                    target = ", ".join(positive_non_ic)
                    ct_list = [ str(by_target[t]) for t in positive_non_ic if is_numeric(by_target[t])]
                    ct = ", ".join(ct_list)
                else:
                    valid = False
                    final_result = 'Invalid minta'
            else:
                # nincs IC a PCR-ben
                if not positive_targets:
                    valid = True
                    final_result = 'negatív'
                else:
                    valid = True
                    final_result = 'pozitív'
                    target = "".join(positive_targets)
                    ct_list = [ str(by_target[t]) for t in positive_targets if is_numeric(by_target[t])]
                    ct = ", ".join(ct_list)

        final_rows.append({
            'well': well,
            'well_position': well_pos,
            'sample_id': sample_id,
            'final_result': final_result,
            'target': target,
            'ct': ct,
            'valid': valid
        })

    final_results = pd.DataFrame(final_rows) 
    return final_results

