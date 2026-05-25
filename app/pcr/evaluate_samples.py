# import libraries
import pandas as pd

### Import other functions
from app.kits.mapping_dye_target import mapping_dye_target
from app.kits.selected_kit import load_selected_kit


# ---------------------------------------------------------------------------
# Helper: targetnevek kinyerése típus szerint a kit JSON-ból
# ---------------------------------------------------------------------------

def get_targets_by_type(kit_targets: dict, target_type: str) -> list[str]:
    """
    Visszaadja azon targetek neveit, amelyek típusa megegyezik a target_type-al.
    Pl. target_type="internal_control" → ["IC"] vagy ["RNase P"]
    """
    return [
        info["target_name"]
        for info in kit_targets.values()
        if info.get("type") == target_type
    ]


# ---------------------------------------------------------------------------
# Helper: illeszkedés vizsgálat
# ---------------------------------------------------------------------------

def matches_rules(neg_flags: dict, rules: dict) -> bool:
    """
    Megvizsgálja, hogy a minta neg_flags dict-je megfelel-e
    a JSON-ban megadott rules dict-nek.

    neg_flags: {target_name: bool}  →  True = negatív, False = pozitív
    rules:     {target_name: bool}  →  True = negatívnak kell lennie
                                       False = pozitívnak kell lennie
    """
    for target, expected_negative in rules.items():
        actual_negative = neg_flags.get(target, None)
        if actual_negative is None:
            return False
        if actual_negative != expected_negative:
            return False
    return True


# ---------------------------------------------------------------------------
# Helper: kontroll minták kiértékelése (NTC, PK, Prep_NTC)
# ---------------------------------------------------------------------------

def evaluate_control(sample_id: str,
                     neg_flags: dict,
                     num_flags: dict,
                     controls: dict,
                     ic_targets: list[str]) -> tuple[bool, str]:
    """
    Visszaadja (valid, final_result) tuple-t a kontroll mintákhoz.

    NTC, PK: teljes egészében JSON rules alapján.
    Prep_NTC: IC-knek pozitívnak kell lenniük, minden más targetnek negatívnak.
    """

    # NTC és PK: JSON controls blokkból jön a szabály
    if sample_id in controls:
        rules = controls[sample_id].get("rules", {})
        if matches_rules(neg_flags, rules):
            return True, f"Valid {sample_id}"
        else:
            return False, f"Invalid {sample_id}"

    # Prep_NTC: IC pozitív + minden más target negatív
    if sample_id == "Prep_NTC":
        non_ic_targets = [t for t in neg_flags if t not in ic_targets]

        if ic_targets:
            ic_positive = all(num_flags.get(t, False) for t in ic_targets)
            others_negative = all(neg_flags.get(t, True) for t in non_ic_targets)

            if ic_positive and others_negative:
                return True, "Valid PrepNTC"
            else:
                return False, "Invalid PrepNTC"
        else:
            # Nincs IC a kitben → minden targetnek negatívnak kell lennie
            if all(neg_flags.get(t, False) for t in neg_flags):
                return True, "Valid PrepNTC (IC nélkül)"
            else:
                return False, "Invalid PrepNTC"

    # Ismeretlen kontroll típus
    return False, f"Ismeretlen kontroll: {sample_id}"


# ---------------------------------------------------------------------------
# Helper: ismeretlen minták kiértékelése a sample_result JSON szabályok alapján
# ---------------------------------------------------------------------------

def evaluate_unknown_sample(neg_flags: dict,
                             num_flags: dict,
                             by_target: dict,
                             sample_result_rules: dict) -> tuple[bool, str, str, str]:
    """
    Visszaadja (valid, final_result, target, ct) tuple-t
    az ismeretlen mintákhoz, JSON-alapú szabályok szerint.

    A kiértékelés sorrendje:
      1. "invalid minta"  → ha illeszkedik: invalid
      2. "negatív minta"  → ha illeszkedik: negatív
      3. "pozitív minta"  → az első illeszkedő pozitív kombináció
      4. fallback         → "Ismeretlen eredmény"
    """

    def is_numeric(v):
        return pd.notnull(pd.to_numeric(v, errors='coerce'))

    # --- 1. Invalid ---
    invalid_rules = sample_result_rules.get("invalid minta", {}).get("rules", {})
    if invalid_rules and matches_rules(neg_flags, invalid_rules):
        return False, "Invalid minta", "", ""

    # --- 2. Negatív ---
    negative_rules = sample_result_rules.get("negatív minta", {}).get("rules", {})
    if negative_rules and matches_rules(neg_flags, negative_rules):
        return True, "negatív", "", ""

    # --- 3. Pozitív ---
    positive_block = sample_result_rules.get("pozitív minta", {})
    for combo_name, combo_data in positive_block.items():
        rules = combo_data.get("rules", {})
        if matches_rules(neg_flags, rules):
            positive_targets = [t for t, expected_neg in rules.items()
                                 if not expected_neg]
            ct_list = [str(by_target[t]) for t in positive_targets
                       if t in by_target and is_numeric(by_target[t])]
            ct = ", ".join(ct_list)
            return True, "pozitív", combo_name, ct

    # --- 4. Fallback ---
    return False, "Ismeretlen eredmény", "", ""


# ---------------------------------------------------------------------------
# Fő függvény
# ---------------------------------------------------------------------------

def evaluate_samples(file,
                     sampleid_df,
                     selected_kit_name,
                     well_col="well",
                     well_position_col="well_position",
                     sample_id="sample_id",
                     cycle_col="cycle",
                     window=9,
                     poly=2):

    # --- PCR adatok előfeldolgozása ---
    pcr_result = mapping_dye_target(file,
                                    sampleid_df,
                                    selected_kit_name,
                                    well_col=well_col,
                                    well_position_col=well_position_col,
                                    sample_id=sample_id,
                                    cycle_col=cycle_col,
                                    window=window,
                                    poly=poly)

    # --- Kit konfiguráció betöltése ---
    selected_kit = load_selected_kit(selected_kit_name)[0]

    kit_targets = selected_kit.get("targets", {})
    controls = selected_kit.get("controls", {})
    sample_result_rules = selected_kit.get("sample_result", {})

    # IC targetnevek kinyerése a JSON type mező alapján
    ic_targets = get_targets_by_type(kit_targets, "internal_control")

    # --- Flag aggregálása well/well_position szinten ---
    # Ha bármelyik csatornában True a flag → "manuális értékelést igényel"
    if "flag" in pcr_result.columns:
        flag_map = (
            pcr_result
            .groupby([well_col, well_position_col])["flag"]
            .any()
            .reset_index()
            .rename(columns={"flag": "_flag_any"})
        )
    else:
        flag_map = None

    # --- Segédfüggvények ---
    def is_negative(v):
        if pd.isnull(v):
            return False
        return str(v).strip().lower().startswith('negat')

    def is_numeric(v):
        return pd.notnull(pd.to_numeric(v, errors='coerce'))

    # --- Kontroll minta azonosítók ---
    control_ids = set(controls.keys()) | {"Prep_NTC"}

    # --- Kiértékelés ---
    final_rows = []
    group_cols = ['well', 'well_position', 'sample_id']

    for (well, well_pos, sid), g in pcr_result.groupby(group_cols):

        by_target = g.set_index('Target')['Result'].to_dict()

        neg_flags = {t: is_negative(v) for t, v in by_target.items()}
        num_flags = {t: is_numeric(v) for t, v in by_target.items()}

        valid = False
        final_result = ""
        target = ""
        ct = ""

        if sid in control_ids:
            valid, final_result = evaluate_control(
                sid, neg_flags, num_flags, controls, ic_targets
            )
        else:
            valid, final_result, target, ct = evaluate_unknown_sample(
                neg_flags, num_flags, by_target, sample_result_rules
            )

        final_rows.append({
            'well': well,
            'well_position': well_pos,
            'sample_id': sid,
            'final_result': final_result,
            'target': target,
            'ct': ct,
            'valid': valid
        })

    final_df = pd.DataFrame(final_rows)

    # --- Flag oszlop hozzáadása ---
    if flag_map is not None:
        final_df = final_df.merge(flag_map, on=[well_col, well_position_col], how="left")
        final_df["flag"] = final_df["_flag_any"].apply(
            lambda x: "manuális értékelést igényel" if x else ""
        )
        final_df = final_df.drop(columns=["_flag_any"])
    else:
        final_df["flag"] = ""

    return final_df
