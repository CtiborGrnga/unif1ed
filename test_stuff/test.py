import requests

def get_latest_session():
    try:
        url = "https://api.openf1.org/v1/sessions"
        response = requests.get(url)
        response.raise_for_status()
        sessions = response.json()

        # Vyfiltruj len sessions s platným session_key
        valid_sessions = [
            s for s in sessions if s.get("session_key") is not None
        ]

        # Ak nič nenájdeme, skončíme
        if not valid_sessions:
            print("❌ Žiadne platné session neboli nájdené.")
            return

        # Vyber poslednú (najnovšiu) session
        latest = valid_sessions[-1]

        print("🆕 Najnovšia session:")
        print(f"  🗓  Dátum:         {latest.get('date', 'N/A')}")
        print(f"  📍 Miesto:        {latest.get('location', 'Unknown')}")
        print(f"  🇨🇴 Krajina:      {latest.get('country_name', 'Unknown Country')}")
        print(f"  🏁 Názov session: {latest.get('session_name', 'Unknown Session')}")
        print(f"  🔑 Session key:   {latest.get('session_key', 'N/A')}")
        print(f"  📅 Rok:           {latest.get('year', 'Unknown')}")

    except Exception as e:
        print(f"❌ Chyba pri získavaní session: {e}")

if __name__ == "__main__":
    get_latest_session()
