import streamlit as st

# ---- "Backend" rész (adat és logika) ----
if "inventory" not in st.session_state:
    st.session_state.inventory = {
        "Alma": 10,
        "Banán": 5,
        "Narancs": 8
    }

def add_fruit(fruit, amount):
    st.session_state.inventory[fruit] += amount


# ---- "Frontend" rész (UI) ----
st.title("🍎 Gyümölcs raktárkészlet")

fruit = st.selectbox(
    "Válassz gyümölcsöt:",
    list(st.session_state.inventory.keys())
)

amount = st.number_input(
    "Mennyiséget adj hozzá:",
    min_value=1,
    step=1
)

if st.button("➕ Hozzáadás"):
    add_fruit(fruit, amount)
    st.success(f"{amount} db {fruit} hozzáadva!")

st.subheader("📦 Aktuális készlet")

for fruit, qty in st.session_state.inventory.items():
    st.write(f"**{fruit}**: {qty} db")
