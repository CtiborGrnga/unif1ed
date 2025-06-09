import fastf1.events
from flask import Flask, render_template, request, jsonify
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import traceback
import numpy as np
import fastf1
from fastf1.ergast import Ergast
import csv

app = Flask(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SEASON = 0
ROUND = 0

def get_current_f1_round_number(season=None):

    if season is None:
        season = datetime.now().year

    try:
        # Získanie kompletného rozvrhu udalostí pre danú sezónu
        schedule = fastf1.events.get_event_schedule(season)
        if schedule.empty:
            return (None, season)
    except Exception as e:
        # Tichá chyba, ak sa nepodarí získať rozvrh
        traceback.print_exc() # Pre debug, ak je potrebné
        return (None, season)

    current_date = datetime.now()

    # Zoradenie udalostí podľa dátumu
    schedule = schedule.sort_values(by='EventDate').reset_index(drop=True)

    current_round_number = None

    for index, event in schedule.iterrows():
        event_race_day = event['EventDate'].to_pydatetime()

        # Definovanie "víkendového okna" (piatok až pondelok)
        weekend_start = event_race_day - timedelta(days=2)
        weekend_end = event_race_day + timedelta(days=1)

        # Ak aktuálny dátum spadá do víkendového okna udalosti
        if weekend_start <= current_date <= weekend_end:
            current_round_number = event['RoundNumber']
            break

        if current_date < weekend_start:
            if index > 0:
                current_round_number = schedule.loc[index - 1]['RoundNumber']
            else:
                current_round_number = None
            break

    if current_round_number is None and not schedule.empty:
        current_round_number = schedule.iloc[-1]['RoundNumber']

    return (current_round_number, season)

if __name__ == "__main__":
    round_num, current_season = get_current_f1_round_number()
    SEASON = current_season
    ROUND = round_num
    if round_num is None:
        round_num = 0
    
#round_num je cislo kola, current_season je aktualny rok sezony
    

def get_drivers_standings(season=SEASON, round=ROUND):
    """Gets the current driver standings from Ergast and returns a Pandas DataFrame."""
    ergast = Ergast()
    try:
        standings = ergast.get_driver_standings(season=season, round=round)
        if standings.content:
            df = pd.DataFrame(standings.content[0])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching driver standings: {e}")
        traceback.print_exc()
        return pd.DataFrame()

def get_latest_session_key():
    try:
        url = "https://api.openf1.org/v1/sessions"
        response = requests.get(url)
        response.raise_for_status()
        sessions = response.json()
        valid_sessions = [s for s in sessions if s.get("session_key") is not None]
        if not valid_sessions:
            return None
        # Zoradíme podľa dátumu a vrátime najnovšiu session_key
        valid_sessions.sort(key=lambda x: x.get("date", ""), reverse=True)
        return valid_sessions[0].get("session_key")
    except Exception as e:
        print(f"Error fetching latest session: {e}")
        traceback.print_exc()
        return None


def calculate_max_points_for_remaining_season(season=SEASON, round=ROUND):
    """Calculates the maximum points possible in the remaining season."""
    try:
        POINTS_FOR_SPRINT = 8 + 25
        POINTS_FOR_CONVENTIONAL = 25

        events = fastf1.events.get_event_schedule(season, backend='ergast')
        events = events[events['RoundNumber'] > round]
        sprint_events = len(events.loc[events["EventFormat"] == "sprint_shootout"])
        conventional_events = len(events.loc[events["EventFormat"] == "conventional"])

        sprint_points = sprint_events * POINTS_FOR_SPRINT
        conventional_points = conventional_events * POINTS_FOR_CONVENTIONAL

        return sprint_points + conventional_points
    except Exception as e:
        print(f"Error calculating max points: {e}")
        traceback.print_exc()
        return 0


def calculate_who_can_win(driver_standings, max_points):
    """Determines which drivers can still win the WDC and adds a 'can_win' column to the DataFrame."""
    if driver_standings.empty:
        return pd.DataFrame()
    try:
        leader_points = int(driver_standings.loc[0]['points'])
        driver_standings['can_win'] = driver_standings.apply(
            lambda row: 'Yes' if int(row["points"]) + max_points >= leader_points else 'No', axis=1
        )
        return driver_standings[['position', 'givenName', 'familyName', 'points', 'can_win']]  # Return only necessary columns
    except Exception as e:
        print(f"Error determining who can win: {e}")
        traceback.print_exc()
        return pd.DataFrame()


def format_lap_time(seconds):
    if seconds is None or pd.isna(seconds):
        return "N/A"
    try:
        if isinstance(seconds, str):
            seconds = float(seconds)
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}:{remaining_seconds:06.3f}"
    except (TypeError, ValueError):
        return str(seconds)


def get_all_sessions(exclude_latest=False):
    try:
        url = "https://api.openf1.org/v1/sessions"
        response = requests.get(url)
        response.raise_for_status()
        sessions = response.json()
        valid_sessions = []
        for s in sessions:
            if s.get("session_key") is not None:
                s["year"] = s.get("year", "Unknown")
                s["country_name"] = s.get("country_name", "Unknown Country")
                s["session_name"] = s.get("session_name", "Unknown Session")
                s["location"] = s.get("location", "Unknown Location")
                s["date"] = s.get("date", "")
                valid_sessions.append(s)

        # Zoradiť sessions podľa dátumu (najnovšie ako prvé)
        valid_sessions.sort(key=lambda x: x.get("date", ""), reverse=True)

        # ❗ Odstrániť najnovšiu session, ak je žiadané
        if exclude_latest and valid_sessions:
            valid_sessions = valid_sessions[1:]

        return valid_sessions
    except Exception as e:
        print(f"Error fetching sessions: {e}")
        traceback.print_exc()
        return []

# ... (existujúce funkcie pred touto) ...

def get_live_position_data(session_key):
    """
    Načíta dáta o pozíciách jazdcov z OpenF1 API pre danú session_key,
    vyberie najnovšiu pozíciu pre každého jazdca a vráti slovník
    {driver_number (str): position (int)}.
    """
    url = "https://api.openf1.org/v1/position"
    params = {"session_key": session_key}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data:
            print(f"No position data for session {session_key}.")
            return {}

        latest_positions_raw = {} # Stores {driver_number: {'position': pos, 'date': datetime_obj}}

        for item in data:
            driver_num_str = str(item.get('driver_number')) # Ensure driver_number is string
            position = item.get('position')
            record_date_str = item.get('date') 

            if driver_num_str is None or position is None or record_date_str is None:
                continue

            try:
                record_date = datetime.fromisoformat(record_date_str.replace('Z', '+00:00'))
                current_position_int = int(position)

                if driver_num_str in latest_positions_raw:
                    if record_date > latest_positions_raw[driver_num_str]['date']:
                        latest_positions_raw[driver_num_str] = {
                            'position': current_position_int,
                            'date': record_date
                        }
                else:
                    latest_positions_raw[driver_num_str] = {
                        'position': current_position_int,
                        'date': record_date
                    }
            except (ValueError, TypeError) as e:
                print(f"Warning: Data issue for driver {driver_num_str} in position API: {e}. Item: {item}")
                continue
        
        # Convert to final {driver_number: position} map
        final_positions_map = {dn: info['position'] for dn, info in latest_positions_raw.items()}
        return final_positions_map

    except requests.exceptions.RequestException as e:
        print(f"Error fetching live position data for session {session_key}: {e}")
        traceback.print_exc()
        return {}
    except ValueError:
        print(f"Error: Invalid JSON data from position API for session {session_key}.")
        traceback.print_exc()
        return {}
    except Exception as e:
        print(f"Unexpected error in get_live_position_data for session {session_key}: {e}")
        traceback.print_exc()
        return {}

# ... (pokračovanie existujúcich funkcií) ...

def get_drivers_data(session_key):
    drivers_path = os.path.join(DATA_DIR, f"drivers_{session_key}.csv")
    print(f"Attempting to load drivers from: {drivers_path}")

    if os.path.exists(drivers_path):
        try:
            print("CSV file exists. Attempting to read...")
            df = pd.read_csv(drivers_path,
                             encoding='utf-8',
                             header=0,
                             keep_default_na=False,
                             na_values=['']
                             )
            print("CSV read successfully.")
            print(f"Columns in CSV: {df.columns.tolist()}")

            for col in ['driver_number', 'broadcast_name', 'team_name']:
                if col not in df.columns:
                    df[col] = 'N/A'

            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].replace({np.nan: None})
                elif pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].apply(lambda x: None if pd.isna(x) else x)

            drivers_data = df.to_dict("records")
            print("Drivers data from CSV (after NaN handling):", drivers_data)
            return drivers_data

        except Exception as e:
            print(f"Error reading drivers CSV: {e}")
            traceback.print_exc()
            print("Falling back to API for drivers.")
            pass

    else:
        print("CSV file does not exist. Fetching from API.")

    try:
        url = "https://api.openf1.org/v1/drivers"
        params = {"session_key": session_key}
        print(f"Fetching drivers from API for session key: {session_key}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        drivers = response.json()

        unique_drivers = {}
        for driver in drivers:
            if 'driver_number' in driver:
                unique_drivers[driver['driver_number']] = driver
        driver_list = list(unique_drivers.values())

        df = pd.DataFrame(driver_list)
        for col in ['driver_number', 'broadcast_name', 'team_name']:
            if col not in df.columns:
                df[col] = 'N/A'

        df.to_csv(drivers_path, index=False)
        drivers_data_api = df.to_dict("records")
        print("Drivers data from API:", drivers_data_api)
        return drivers_data_api

    except Exception as e:
        print(f"Error fetching drivers from API: {e}")
        traceback.print_exc()
        return []


def get_lap_times_for_session(session_key, drivers):
    laps_path = os.path.join(DATA_DIR, f"laps_{session_key}.csv")
    if os.path.exists(laps_path):
        try:
            df = pd.read_csv(laps_path)
            df['lap_duration'] = pd.to_numeric(df['lap_duration'], errors='coerce')
            df['lap_time'] = df['lap_duration'].apply(format_lap_time)
            return df
        except Exception as e:
            print(f"Error reading laps CSV: {e}")
            traceback.print_exc()
            pass

    all_laps = []
    for driver in drivers:
        driver_number = driver.get("driver_number")
        if not driver_number:
            continue
        try:
            url = "https://api.openf1.org/v1/laps"
            params = {"session_key": session_key, "driver_number": driver_number}
            response = requests.get(url, params=params)
            response.raise_for_status()
            laps = response.json()
            if isinstance(laps, dict):
                laps = [laps]
            df = pd.DataFrame(laps)
            df["driver_number"] = driver_number
            if "lap_duration" in df.columns:
                df["lap_time"] = df["lap_duration"].apply(format_lap_time)
            all_laps.append(df)
        except Exception as e:
            print(f"Error fetching lap times for driver {driver_number}: {e}")
            traceback.print_exc()

    if not all_laps:
        return pd.DataFrame()

    full_df = pd.concat(all_laps, ignore_index=True)
    full_df.to_csv(laps_path, index=False)
    return full_df

def get_team_radio_from_api(session_key, driver_number=None):
    """
    Fetches team radio data directly from the OpenF1 API.
    Can filter by driver_number. Enriches data with session and driver names.
    """
    try:
        url = "https://api.openf1.org/v1/team_radio"
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number

        response = requests.get(url, params=params)
        response.raise_for_status()
        radio_data = response.json()

        if isinstance(radio_data, dict): # Ensure it's a list
            radio_data = [radio_data]

        # Enrich data with driver name and session name for display
        all_sessions = get_all_sessions()
        session_info = next((s for s in all_sessions if s['session_key'] == session_key), None)
        session_name = session_info['session_name'] if session_info else 'Unknown Session'

        all_drivers = get_drivers_data(session_key)
        driver_map = {d['driver_number']: d['broadcast_name'] for d in all_drivers}

        for radio_msg in radio_data:
            radio_msg['session_name'] = session_name
            dr_num = radio_msg.get('driver_number')
            radio_msg['driver_name'] = driver_map.get(dr_num, f"Driver {dr_num}") if dr_num else 'Unknown Driver'
            # Format date for display
            if 'date' in radio_msg and radio_msg['date']:
                try:
                    dt_object = datetime.fromisoformat(radio_msg['date'].replace('Z', '+00:00'))
                    radio_msg['formatted_date'] = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
                except ValueError:
                    radio_msg['formatted_date'] = radio_msg['date'] # Fallback
            else:
                radio_msg['formatted_date'] = 'N/A'

        return radio_data
    except Exception as e:
        print(f"Error fetching team radio from API for session {session_key}, driver {driver_number}: {e}")
        traceback.print_exc()
        return []


def get_team_radio_data(session_key, driver_number=None):
    """
    Retrieves team radio data, prioritizing CSV.
    This function is for historical data; it fetches from API and saves to CSV if not found.
    """
    radio_path = os.path.join(DATA_DIR, f"radio_{session_key}.csv")

    if os.path.exists(radio_path):
        try:
            df = pd.read_csv(radio_path)
            # Convert back to list of dicts
            radio_data = df.to_dict("records")
            # Ensure data is enriched if loaded from CSV (e.g., if columns were missing)
            all_sessions = get_all_sessions()
            session_info = next((s for s in all_sessions if s['session_key'] == session_key), None)
            session_name = session_info['session_name'] if session_info else 'Unknown Session'

            all_drivers = get_drivers_data(session_key)
            driver_map = {d['driver_number']: d['broadcast_name'] for d in all_drivers}

            for radio_msg in radio_data:
                radio_msg['session_name'] = session_name
                dr_num = radio_msg.get('driver_number')
                radio_msg['driver_name'] = driver_map.get(dr_num, f"Driver {dr_num}") if dr_num else 'Unknown Driver'
                if 'date' in radio_msg and radio_msg['date']:
                    try:
                        dt_object = datetime.fromisoformat(radio_msg['date'].replace('Z', '+00:00'))
                        radio_msg['formatted_date'] = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
                    except ValueError:
                        radio_msg['formatted_date'] = radio_msg['date'] # Fallback
                else:
                    radio_msg['formatted_date'] = 'N/A'

            if driver_number:
                radio_data = [r for r in radio_data if r.get('driver_number') == driver_number]

            return radio_data
        except Exception as e:
            print(f"Error reading radio CSV for session {session_key}: {e}")
            traceback.print_exc()
            pass # Fall through to API fetch

    # If CSV not found or failed, fetch from API and save
    radio_data_from_api = get_team_radio_from_api(session_key) # Fetch all for session to cache
    if radio_data_from_api:
        df = pd.DataFrame(radio_data_from_api)
        # Drop columns that might cause issues or are not needed for CSV cache
        df_to_save = df.drop(columns=['session_name', 'driver_name', 'formatted_date'], errors='ignore')
        df_to_save.to_csv(radio_path, index=False)

    if driver_number and radio_data_from_api:
        return [r for r in radio_data_from_api if r.get('driver_number') == driver_number]
    return radio_data_from_api


def get_live_team_radio_data(session_key, driver_number=None):
    """
    Fetches live team radio data directly from the API without CSV interaction.
    """
    return get_team_radio_from_api(session_key, driver_number)

def get_qualifying_results(session_key):
    """Gets and formats qualifying results for a given session, sorted by live positions."""
    try:
        url_laps = "https://api.openf1.org/v1/laps"
        url_drivers = "https://api.openf1.org/v1/drivers"
        params = {"session_key": session_key}

        # Fetch laps data
        response_laps = requests.get(url_laps, params=params)
        response_laps.raise_for_status()
        laps_data = response_laps.json()
        df_laps = pd.DataFrame(laps_data)
        df_laps = df_laps[df_laps['lap_duration'].notna()]  # Filter out laps without time

        # Fetch drivers data
        response_drivers = requests.get(url_drivers, params=params)
        response_drivers.raise_for_status()
        drivers_data = response_drivers.json()
        # Ensure driver_number is string for consistent mapping
        driver_map = {str(d['driver_number']): d for d in drivers_data if 'driver_number' in d}

        # Get fastest lap for each driver
        fastest_laps = df_laps.groupby('driver_number')['lap_duration'].min().reset_index()

        # Add driver names and team names
        fastest_laps['Driver'] = fastest_laps['driver_number'].apply(
            lambda x: f"{driver_map.get(str(x), {}).get('first_name', '')} {driver_map.get(str(x), {}).get('last_name', '')}".strip()
        )
        fastest_laps['Team'] = fastest_laps['driver_number'].apply(
            lambda x: driver_map.get(str(x), {}).get('team_name', 'N/A'))

        # --- NOVÁ ČASŤ PRE ZÍSKANIE A APLIKOVANIE LIVE POZÍCIÍ ---
        live_positions_map = get_live_position_data(session_key)

        # Map live positions to fastest_laps DataFrame
        # Pre jazdcov, ktorí nemajú live pozíciu (napr. neboli na trati alebo API nevrátilo dáta),
        # priradíme veľké číslo, aby sa zoradili na koniec.
        fastest_laps['live_position'] = fastest_laps['driver_number'].apply(
            lambda x: live_positions_map.get(str(x), 9999) # Prekonvertuj driver_number na string pre lookup
        )

        # Zoradíme najprv podľa live_position, potom podľa lap_duration pre prípady zhodných pozícií
        # alebo pre jazdcov bez live pozície (ktorí budú na konci).
        fastest_laps = fastest_laps.sort_values(by=['live_position', 'lap_duration']).reset_index(drop=True)
        # --- KONIEC NOVEJ ČASTI ---

        # Format lap times for display
        fastest_laps['LapTime'] = fastest_laps['lap_duration'].apply(format_lap_time)

        # Select desired columns for output. 'Pos' column in live.html is generated by loop.index.
        return fastest_laps[['Driver', 'Team', 'LapTime']].to_dict(orient='records')

    except Exception as e:
        print(f"Error fetching qualifying results: {e}")
        traceback.print_exc()
        return []
    


def get_circuit_details_from_csv(circuit_short_name):
    """
    Reads circuit details from a CSV file located in data/circuits/.
    The CSV is expected to have headers in the first row and values in the second.
    Returns a dictionary of circuit properties.
    """
    # Použite app.root_path pre získanie absolútnej cesty, aby ste sa vyhli problémom s relatívnymi cestami
    csv_file_path = os.path.join(app.root_path, DATA_DIR, 'circuits', f"{circuit_short_name}.csv")
    circuit_info = {}
    print(f"Attempting to read circuit CSV from: {csv_file_path}") # Pre ladenie
    if os.path.exists(csv_file_path):
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                csv_reader = csv.reader(csvfile)
                
                # Prečíta prvý riadok ako hlavičky/kľúče
                headers = next(csv_reader) 
                
                # Prečíta druhý riadok ako hodnoty
                values = next(csv_reader)  

                # Spojí hlavičky s hodnotami do slovníka
                for i in range(len(headers)):
                    if i < len(values): # Uistite sa, že existuje zodpovedajúca hodnota
                        circuit_info[headers[i].strip()] = values[i].strip()
            print(f"Successfully loaded circuit info: {circuit_info}") # Pre ladenie
        except StopIteration:
            print(f"CSV file {csv_file_path} is empty or contains only headers.")
        except Exception as e:
            print(f"Error reading circuit CSV {csv_file_path}: {e}")
            traceback.print_exc()
    else:
        print(f"Circuit CSV file not found: {csv_file_path}") # Pre ladenie
    return circuit_info


def get_race_control_data(session_key):
    """
    Načíta dáta z OpenF1 race_control API pre danú session_key.
    """
    url = "https://api.openf1.org/v1/race_control"
    params = {"session_key": session_key}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Zoradíme dáta od najnovších po najstaršie
        data.sort(key=lambda x: x.get('date', ''), reverse=True)

        processed_data = []
        for item in data:
            formatted_date = 'N/A'
            if 'date' in item and item['date']:
                try:
                    dt_object = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                    formatted_date = dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
                except ValueError:
                    formatted_date = item['date']

            processed_data.append({
                "date": formatted_date,
                "category": item.get("category", "N/A"),
                "message": item.get("message", "N/A"),
                "flag": item.get("flag", "N/A"),
                "scope": item.get("scope", "N/A"),
                "sector": item.get("sector", "N/A")
            })
        return processed_data
    except requests.exceptions.RequestException as e:
        print(f"Chyba pri načítavaní race control dát pre session {session_key}: {e}")
        traceback.print_exc()
        return []
    except Exception as e:
        print(f"Neočakávaná chyba v get_race_control_data pre session {session_key}: {e}")
        traceback.print_exc()
        return []

# --- Flask Routes ---
@app.route("/")
def index():
    """Renders the index page with WDC standings, attempting to gracefully handle errors with ROUND."""
    current_round = ROUND  # Store the original ROUND value
    error_message = None

    for attempt in range(2):  # Try twice: once with ROUND, once with ROUND - 1
        try:
            driver_standings_df = get_drivers_standings(round=current_round)
            if driver_standings_df.empty:
                raise ValueError(f"No driver standings data available for round {current_round}.")

            max_points = calculate_max_points_for_remaining_season(round=current_round)
            standings_with_win_df = calculate_who_can_win(driver_standings_df, max_points)
            standings_data = standings_with_win_df.to_dict(orient='records')
            return render_template("index.html", standings=standings_data)

        except Exception as e:
            print(f"Error fetching standings for round {current_round}: {e}")
            traceback.print_exc()
            error_message = f"Failed to load WDC standings for round {current_round}."
            if attempt == 0 and current_round > 1:  # Only try ROUND - 1 if it's not the first round
                current_round -= 1
            else:
                break  # Exit the loop if the second attempt fails or ROUND is 1

    return render_template("index.html", error=error_message), 500


@app.route("/laps")
def laps():
    return render_template("laps.html")

@app.route("/teamradio")
def teamradio():
    return render_template("teamradio.html")


@app.route("/wdc_standings")
def wdc_standings():
    """This route is no longer the primary WDC display."""
    return render_template("message.html", message="WDC Standings are now displayed on the home page.")

@app.route("/race_control")
def race_control_page():
    """Rendruje stránku race_control.html."""
    return render_template("race_control.html")

@app.route("/live")
def live_page():
    try:
        url = "https://api.openf1.org/v1/sessions"
        response = requests.get(url)
        response.raise_for_status()
        sessions = response.json()
        valid_sessions = [s for s in sessions if s.get("session_key") is not None]
        valid_sessions.sort(key=lambda x: x.get("date", ""))
        latest = valid_sessions[-1] if valid_sessions else None

        session_key = latest.get("session_key") if latest else None
        qualifying_results = get_qualifying_results(session_key) if session_key else []

        circuit_info = None
        if latest and latest.get("circuit_short_name"):
            circuit_info = get_circuit_details_from_csv(latest["circuit_short_name"])

        return render_template("live.html", latest_session=latest, qualifying_results=qualifying_results, circuit_info=circuit_info)
    except Exception as e:
        traceback.print_exc()
        return render_template("live.html", latest_session=None, qualifying_results=[], error="Nepodarilo sa načítať dáta.")


@app.route("/get_sessions", methods=["GET"])
def get_sessions_api():
    sessions = get_all_sessions()
    if sessions:
        # odstráni poslednú session (ktorá bude v HTML ako prvá – najnovšia)
        sessions = sessions[:-1]
    return jsonify({"sessions": sessions})

@app.route("/get_sessions_for_radio", methods=["GET"])
def get_sessions_for_radio_api():
    sessions = get_all_sessions()
    return jsonify({"sessions": sessions})


@app.route("/get_drivers", methods=["GET"])
def get_drivers_api():
    session_key = request.args.get("session_key")
    if not session_key:
        return jsonify({"error": "Missing session key."}), 400
    try:
        drivers_data = get_drivers_data(int(session_key))
        return jsonify({"drivers": drivers_data})
    except Exception as e:
        print(f"Error in get_drivers_api: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/driver_laps", methods=["POST"])
def driver_laps():
    session_key = request.form.get("session_key")
    driver_number = request.form.get("driver_number")
    if not session_key or not driver_number:
        return jsonify({"error": "Missing parameters."}), 400

    try:
        session_key = int(session_key)
        driver_number = int(driver_number)

        drivers_data = get_drivers_data(session_key)

        if not drivers_data:
            return jsonify({"laps": [], "error": "No driver data available for this session."})

        lap_df = get_lap_times_for_session(session_key, drivers_data)

        driver_laps = lap_df[lap_df["driver_number"] == driver_number].copy()

        for col in driver_laps.columns:
            driver_laps[col] = driver_laps[col].replace({np.nan: None})

            if pd.api.types.is_timedelta64_dtype(driver_laps[col]):
                driver_laps[col] = driver_laps[col].astype(str)

            if pd.api.types.is_numeric_dtype(driver_laps[col]):
                driver_laps[col] = driver_laps[col].apply(lambda x: x.item() if pd.notna(x) and isinstance(x, np.number) else x)

            if pd.api.types.is_datetime64_any_dtype(driver_laps[col]):
                driver_laps[col] = driver_laps[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)

        columns_to_display = [col for col in driver_laps.columns if col != "lap_duration"]
        laps_data = driver_laps[columns_to_display].to_dict("records")

        return jsonify({"laps": laps_data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/team_radio_data", methods=["POST"])
def team_radio_data():
    """
    API endpoint to get team radio data.
    This endpoint handles historical data (CSV caching).
    """
    session_key = request.form.get("session_key")
    driver_number = request.form.get("driver_number") # Optional driver filter
    if not session_key:
        return jsonify({"error": "Missing session key."}), 400

    try:
        session_key = int(session_key)
        driver_number = int(driver_number) if driver_number else None

        radio_messages = get_team_radio_data(session_key, driver_number)
        return jsonify({"radio_messages": radio_messages})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/live_team_radio_data", methods=["POST"])
def live_team_radio_data():
    """
    API endpoint to get live team radio data directly from the API.
    This endpoint is for polling during live sessions.
    """
    session_key = request.form.get("session_key")
    driver_number = request.form.get("driver_number") # Optional driver filter
    if not session_key:
        return jsonify({"error": "Missing session key."}), 400

    try:
        session_key = int(session_key)
        driver_number = int(driver_number) if driver_number else None

        radio_messages = get_live_team_radio_data(session_key, driver_number)
        return jsonify({"radio_messages": radio_messages})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/live_drivers", methods=["GET"])
def live_drivers():
    try:
        # Najnovšia session
        url = "https://api.openf1.org/v1/sessions"
        response = requests.get(url)
        response.raise_for_status()
        sessions = response.json()
        valid = [s for s in sessions if s.get("session_key") is not None]
        valid.sort(key=lambda x: x.get("date", ""))
        latest = valid[-1]
        session_key = latest.get("session_key")

        # Live dáta jazdcov
        url = "https://api.openf1.org/v1/drivers"
        drivers_response = requests.get(url, params={"session_key": session_key})
        drivers_response.raise_for_status()
        drivers = drivers_response.json()

        unique = {}
        for d in drivers:
            if 'driver_number' in d:
                unique[d['driver_number']] = d

        return jsonify({"session_key": session_key, "drivers": list(unique.values())})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route("/live_laps", methods=["POST"])
def live_laps():
    try:
        session_key = request.form.get("session_key")
        driver_number = request.form.get("driver_number")

        if not session_key or not driver_number:
            return jsonify({"error": "Chýba session_key alebo driver_number"}), 400

        url = "https://api.openf1.org/v1/laps"
        params = {"session_key": session_key, "driver_number": driver_number}
        response = requests.get(url, params=params)
        response.raise_for_status()
        laps = response.json()

        processed = []
        for lap in laps:
            # Výpočet lap_time
            lap_time = "N/A"
            try:
                sec = float(lap.get("lap_duration", 0))
                minutes = int(sec // 60)
                rem_sec = sec % 60
                lap_time = f"{minutes}:{rem_sec:06.3f}"
            except:
                pass

            processed.append({
                "lap_number": lap.get("lap_number"),
                "lap_time": lap_time,
                "duration_sector_1": lap.get("duration_sector_1"),
                "duration_sector_2": lap.get("duration_sector_2"),
                "duration_sector_3": lap.get("duration_sector_3"),
                "is_pit_out_lap": lap.get("is_pit_out_lap"),
                "st_speed": lap.get("st_speed"),
            })

        return jsonify({"laps": processed})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/get_race_control_events", methods=["POST"])
def get_race_control_events():
    """
    API endpoint na získanie race control dát pre danú session_key.
    """
    session_key = request.form.get("session_key")
    if not session_key:
        return jsonify({"error": "Chýba session_key."}), 400

    try:
        session_key = int(session_key)
        race_control_events = get_race_control_data(session_key)
        return jsonify({"events": race_control_events})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run()