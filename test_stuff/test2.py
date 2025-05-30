"""Qualifying results overview
==============================

Plot the qualifying result with visualization the fastest times using OpenF1 API data.
"""

import pandas as pd
import requests

def get_session_data(session_key):
    """Get session information from OpenF1 API"""
    url = "https://api.openf1.org/v1/sessions"
    params = {"session_key": session_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    sessions = response.json()
    if not sessions:
        raise ValueError(f"No session found with key {session_key}")
    return sessions[0]

def get_laps_data(session_key):
    """Get all laps data for a session from OpenF1 API"""
    url = "https://api.openf1.org/v1/laps"
    params = {"session_key": session_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_drivers_data(session_key):
    """Get drivers data for a session from OpenF1 API"""
    url = "https://api.openf1.org/v1/drivers"
    params = {"session_key": session_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def format_lap_time(lap_time_seconds):
    """Convert lap time in seconds to minutes:seconds.milliseconds format"""
    if lap_time_seconds is None:
        return "N/A"
    minutes = int(lap_time_seconds // 60)
    seconds = lap_time_seconds % 60
    return f"{minutes}:{seconds:06.3f}"

def print_qualifying_results(session_key):
    # Get session information
    session = get_session_data(session_key)

    # Get all laps data
    laps_data = get_laps_data(session_key)

    # Get drivers data
    drivers_data = get_drivers_data(session_key)

    # Create a mapping from driver_number to driver details
    driver_map = {str(d['driver_number']): d for d in drivers_data}

    # Convert laps data to DataFrame
    df = pd.DataFrame(laps_data)

    # Filter out laps without time
    df = df[df['lap_duration'].notna()]

    # Get fastest lap for each driver
    fastest_laps = df.groupby('driver_number')['lap_duration'].min().reset_index()

    # Add driver names and team names
    fastest_laps['Driver'] = fastest_laps['driver_number'].apply(
        lambda x: f"{driver_map[str(x)]['first_name']} {driver_map[str(x)]['last_name']}")
    fastest_laps['Team'] = fastest_laps['driver_number'].apply(
        lambda x: driver_map[str(x)]['team_name'])

    # Sort by lap time
    fastest_laps = fastest_laps.sort_values(by='lap_duration').reset_index(drop=True)

    # Format lap times for display
    fastest_laps['LapTime'] = fastest_laps['lap_duration'].apply(format_lap_time)

    # Title
    event_name = session.get('meeting_name', 'Unknown Event')
    session_name = session.get('session_name', 'Unknown Session')

    print(f"{event_name} - {session_name} - Qualifying Results\n")
    print("Pos.  Driver                  Team                      Lap Time")
    print("----  ----------------------  ------------------------  ----------")

    for i, row in fastest_laps.iterrows():
        print(f"{i+1:4}.  {row['Driver']:<22}  {row['Team']:<24}  {row['LapTime']}")

if __name__ == "__main__":
    session_key = input("Enter OpenF1 session key: ")
    print_qualifying_results(session_key)