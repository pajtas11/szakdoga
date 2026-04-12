#import libraries
import json
import pandas as pd

# ### Load selected kit
from config import PCR_KITS_JSON_PATH


def load_selected_kit(selected_kit_name: str):
    with open(PCR_KITS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    kits = data.get("kits", {})

    if selected_kit_name not in kits:
        raise ValueError(f"A kiválasztott kit nem található: {selected_kit_name}")

    kit_config = kits[selected_kit_name]

    # Dye → Target mapping létrehozása
    dye_target_map = {
        dye: kit_config["targets"][dye]["target_name"]
        for dye in kit_config["targets"]
    }
    dyes = list(dye_target_map.keys())

    controls = list(kit_config['controls'].keys())

    return kit_config, dye_target_map, dyes, controls


def kit_info(selected_kit_name: str):
    if not selected_kit_name:
        return None
    config = load_selected_kit(selected_kit_name)[0]
    targets = config["targets"]

    mapping = []

    for dye, info in targets.items():
        target_name = info["target_name"]
        mapping.append(f"{target_name} ({dye}) ")

    kit_info = {
        'kit name ': config['kit_name'],
        'manufacturer': config['manufacturer'],
        'catalog_number': config['catalog_number'],
        'target': mapping
    }
    rows = []

    for key, value in kit_info.items():
        # Ha lista, alakítsuk stringgé
        if isinstance(value, list):
            value = ", ".join(value)

        rows.append({
            "Paraméter": key,
            "Érték": value
                })

    df = pd.DataFrame(rows)
    return df