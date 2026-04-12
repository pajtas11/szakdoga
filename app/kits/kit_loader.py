###load available kits 
import json
from config import PCR_KITS_JSON_PATH


def load_available_kits():
    with open(PCR_KITS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return list(data["kits"].keys())
