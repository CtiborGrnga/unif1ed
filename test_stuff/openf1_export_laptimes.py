import requests
import pandas as pd

# 👉 Získaj session key od používateľa
session_key = input("Zadaj session_key (napr. 9980 pre Imola FP1 2025): ")

try:
    session_key = int(session_key)
except ValueError:
    print("❌ Neplatné číslo session_key.")
    exit()

# 👉 Krok 1: Získaj všetkých jazdcov v danej session
drivers_url = "https://api.openf1.org/v1/drivers"
drivers_params = {"session_key": session_key}
drivers_response = requests.get(drivers_url, params=drivers_params)
drivers_data = drivers_response.json()

if not drivers_data:
    print(f"❌ Žiadni jazdci nenájdení pre session_key = {session_key}")
    exit()

drivers_df = pd.DataFrame(drivers_data)
if "driver_number" not in drivers_df.columns:
    print("❌ Dáta o jazdcoch neobsahujú 'driver_number'.")
    exit()

driver_numbers = drivers_df["driver_number"].dropna().unique()

# 👉 Krok 2: Pre každého jazdca stiahni kolá
all_laps = []

for driver_number in driver_numbers:
    laps_url = "https://api.openf1.org/v1/laps"
    laps_params = {
        "session_key": session_key,
        "driver_number": driver_number
    }
    laps_response = requests.get(laps_url, params=laps_params)
    laps_data = laps_response.json()

    if laps_data:
        df = pd.DataFrame(laps_data)
        df["driver_number"] = driver_number  # priradíme späť jazdca
        all_laps.append(df)

# 👉 Spoj všetky dáta do jedného DataFrame
if not all_laps:
    print(f"❌ Žiadne kolá nenájdené pre žiadneho jazdca v session {session_key}.")
else:
    full_df = pd.concat(all_laps, ignore_index=True)

    # Vyber relevantné stĺpce (len ak existujú)
    columns_to_show = ["driver_number", "lap_number", "lap_duration", "stint_number",
                       "compound", "is_pit_out_lap", "is_pit_in_lap", "is_valid"]
    available_columns = [col for col in columns_to_show if col in full_df.columns]
    full_df = full_df[available_columns]
    full_df = full_df.sort_values(["driver_number", "lap_number"])

    # 👉 Export do CSV
    output_file = f"laps_all_drivers_{session_key}.csv"
    full_df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"✅ Dáta boli uložené do súboru: {output_file}")
