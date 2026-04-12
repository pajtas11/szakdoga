#Minta azonosítók és kontrollok összefésülése
import pandas as pd

def well_position_to_well(well_position: str) -> int:
    # Szétbontás (pl. "M6" → "M" és "6")
    row_letter = well_position[0].upper()
    col_number = int(well_position[1:])
    
    # Sor index meghatározása (A=0, B=1, ..., P=15)
    row_index = ord(row_letter) - ord('A')
    
    # Validáció
    if row_index < 0 or row_index > 15:
        raise ValueError("Érvénytelen sor (A-P lehet)")
    if col_number < 1 or col_number > 24:
        raise ValueError("Érvénytelen oszlop (1-24 lehet)")
    
    # Well sorszám kiszámítása
    well = row_index * 24 + col_number
    
    return well

def finalize_plate_layout(sampleid_df, control_map):
    """
    Összefésüli a mintaazonosítókat és a kontrollokat.
    A kontrollok felülírják a mintaazonosítót a megadott well_position helyeken.
    """
    if sampleid_df is None:
        return None

    # Másolat készítése, hogy ne az eredeti DF-et módosítsuk
    final_df = sampleid_df.copy()
    
    # Új oszlop a típusnak (alapértelmezett: Sample)
    final_df['well_type'] = 'Sample'

    # Kontrollok rögzítése
    # A control_map felépítése: { "A1": "NTC", "B12": "PTC" }
    for position, control_name in control_map.items():
        # Megkeressük a sort, ahol a well_position egyezik az EDS-ben is használt A1 formátummal
        mask = final_df['well_position'] == position
        
        if mask.any():
            # Ha van ilyen sor (pl. az általános listában), felülírjuk a nevet
            final_df.loc[mask, 'sample_id'] = control_name
            final_df.loc[mask, 'well_type'] = 'Control'
        else:
            # Ha olyan well-t jelöltél ki kontrollnak, ami nincs a listában (pl. üres volt)
            # Ez ritka, de így biztonságos
            new_row = pd.DataFrame([{
                'well': well_position_to_well(position),
                'well_position': position,
                'sample_id': control_name,
                'well_type': 'Control'
            }])
            final_df = pd.concat([final_df, new_row], ignore_index=True)

    return final_df