import requests
import pandas as pd

# API volanie
url = "https://api.openf1.org/v1/sessions"
response = requests.get(url)
sessions = response.json()

# Filtrovanie na rok 2025 a platné session_key
sessions_2025 = [
    s for s in sessions
    if s.get("year") == 2025 and s.get("session_key") is not None
]

# Konverzia na DataFrame
df = pd.DataFrame(sessions_2025)

# Over dostupné stĺpce
required_columns = ["session_key", "meeting_name", "session_name", "date", "location"]
available_columns = [col for col in required_columns if col in df.columns]

# Vyber len dostupné stĺpce
df = df[available_columns]

# Spracovanie dátumu
if "date" in df.columns:
    df = df[df["date"].notna()]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

# Výpis dát
print(df.to_string(index=False))
