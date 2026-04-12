#import libraries
import zipfile
import xml.etree.ElementTree as ET
import io
import pandas as pd
import numpy as np

# data_loader függvény
def eds_extract(file):
    xml_path = "apldbio/sds/multicomponentdata.xml"
    rows = []

    try:
        with zipfile.ZipFile(file, 'r') as z:
            try:
                xml_data = z.read(xml_path)
            except KeyError:
                raise FileNotFoundError(
                    f"Hiba: az EDS fájl nem tartalmazza a szükséges XML-t: {xml_path}"
                )

    except zipfile.BadZipFile:
        raise ValueError("Hiba: a megadott fájl nem érvényes EDS (nem ZIP formátum).")

    # XML feldolgozás
    try:
        root = ET.parse(io.BytesIO(xml_data)).getroot()
    except ET.ParseError:
        raise ValueError("Hiba: a multicomponentdata.xml nem érvényes XML.")

    dye_map = {}

    for dye_data in root.iter("DyeData"):
        well_index = int(dye_data.attrib.get("WellIndex", -1))
        dye_list_elem = dye_data.find("DyeList")
        if dye_list_elem is None:
            continue

        dyes = [d.strip() for d in dye_list_elem.text.strip("[]").split(",")]
        if len(dyes) > 2:
            dye_map[well_index] = dyes

    for signal_data in root.iter("SignalData"):
        well_index = int(signal_data.attrib.get("WellIndex", -1))
        dyes = dye_map.get(well_index)

        if dyes is None:
            continue

        cycle_data_elements = signal_data.findall("CycleData")

        for dye_idx, cycle_data in enumerate(cycle_data_elements):
            if dye_idx >= len(dyes):
                continue

            dye = dyes[dye_idx]
            values = [float(v) for v in cycle_data.text.strip("[]").split(",")]

            for cycle_idx, value in enumerate(values):
                rows.append({
                    "well": well_index + 1,
                    "cycle": cycle_idx + 1,
                    "dye": dye,
                    "data": value
                })

    if not rows:
        raise ValueError("Hiba: nem sikerült multicomponent adatot kinyerni az EDS-ből.")
    
    raw_data = pd.DataFrame(rows)
    
    dye_unique = raw_data['dye'].unique().tolist()

    #well position hozzáadása
    row = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P']
    column = list(range(1,25))
    well_pos = {}
    a = 1
    for j in row:
        for i in range(1,25): 
            well_pos[a] = j+str(i)
            a = a+1

    raw_data['well_position'] = raw_data['well'].map(well_pos)
    
    #pivot dataframe
    eds_extract_result = raw_data.pivot(index=('well','well_position','cycle',), columns='dye', values='data')
    eds_extract_result = eds_extract_result.reset_index()


    return eds_extract_result 

