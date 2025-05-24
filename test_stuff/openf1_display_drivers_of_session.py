import requests
import pandas as pd

# Zadáme session_key pre FP1 v Imole 2025
fp1_session_key = 9980  # ← uprav podľa potreby

# Zavoláme API pre driverov
url = "https://api.openf1.org/v1/drivers"
params = {"session_key": fp1_session_key}
response = requests.get(url, params=params)
drivers = response.json()

# Skontrolujeme, či vôbec niečo prišlo
if not drivers:
    print("❌ Žiadni jazdci nájdení pre FP1 Imola 2025 (session_key =", fp1_session_key, ")")
else:
    # Konverzia na DataFrame
    df = pd.DataFrame(drivers)

    print("\n🧪 Stĺpce dostupné v odpovedi API:")
    print(df.columns.tolist())

    # Bezpečne vyber stĺpce, ktoré existujú
    columns_to_show = ["driver_number", "broadcast_name", "team_name", "session_key"]
    available_columns = [col for col in columns_to_show if col in df.columns]
    df = df[available_columns]

    # Odstráň duplicity podľa čísla jazdca (ak existujú)
    if "driver_number" in df.columns:
        df = df.drop_duplicates(subset=["driver_number"])
        df = df.sort_values("driver_number")

    # Výpis do konzoly
    print("\n🔧 Jazdci v FP1 – Imola 2025:\n")
    print(df.to_string(index=False))
