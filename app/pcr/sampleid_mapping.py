#import libraries
import pandas as pd
import numpy as np
from app.pcr.data_loader import eds_extract 

def mapping_sampleid(file, sampleid_df):
    
    # ellenőrizzük, hogy megvannak-e a szükséges oszlopok
    required_cols = {"well_position", "sample_id"}
    if not required_cols.issubset(sampleid_df.columns):
        raise ValueError(f"A CSV-nek tartalmaznia kell ezeket az oszlopokat: {required_cols}")

    sampleid_map = dict(zip(sampleid_df["well_position"], sampleid_df["sample_id"]))

    eds_extract_result_mapped = eds_extract(file)
    eds_extract_result_mapped['sample_id'] = eds_extract_result_mapped['well_position'].map(sampleid_map)
    return eds_extract_result_mapped 

