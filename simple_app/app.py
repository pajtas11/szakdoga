import streamlit as st
import pandas as pd
from analysis.math_logic import calculate_mean

st.title("Egyszerű görbe elemző app")

raw_input = st.text_input(
    "Adj meg számokat vesszővel elválasztva",
    value="1,2,3,4,5"
)

values = [float(x) for x in raw_input.split(",")]

if st.button("Elemzés"):
    mean_value = calculate_mean(values)

    df = pd.DataFrame({
        "index": range(len(values)),
        "value": values
    })

    st.line_chart(df.set_index("index"))
    st.success(f"Átlag: {mean_value:.2f}")
