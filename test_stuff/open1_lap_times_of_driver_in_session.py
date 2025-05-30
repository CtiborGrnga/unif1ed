import requests
import pandas as pd

# 🔢 Parametre
session_key = 9980          # ← zadaj podľa potreby
driver_number = 4           # ← napr. Norris

# 🔁 Zavolaj API pre kolá
url = "https://api.openf1.org/v1/laps"
params = {
    "session_key": session_key,
    "driver_number": driver_number
}

response = requests.get(url, params=params)
laps = response.json()

# ⚠️ Skontroluj, či sú dostupné dáta
if not laps:
    print(f"❌ Žiadne kolá pre jazdca #{driver_number} v session {session_key}.")
else:
    df = pd.DataFrame(laps)

    # Vyber relevantné stĺpce (ak existujú)
    columns_to_show = ["lap_number", "lap_duration", "stint_number", "compound", "is_pit_out_lap", "is_pit_in_lap", "is_valid"]
    available_columns = [col for col in columns_to_show if col in df.columns]
    df = df[available_columns]

    # Zoradenie podľa čísla kola
    df = df.sort_values("lap_number")

    # Výpis
    print(f"\n🟢 Všetky kolá jazdca #{driver_number} – session {session_key}:\n")
    print(df.to_string(index=False))
