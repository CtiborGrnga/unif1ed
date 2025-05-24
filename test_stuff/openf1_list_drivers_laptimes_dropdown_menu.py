import requests
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

class F1LapTimesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("F1 Lap Times Viewer")
        self.root.geometry("1000x600")
        
        # Session selection frame
        self.session_frame = tk.Frame(root, padx=10, pady=10)
        self.session_frame.pack(fill=tk.X)
        
        tk.Label(self.session_frame, text="Enter Session Key:").pack(side=tk.LEFT)
        self.session_entry = tk.Entry(self.session_frame, width=15)
        self.session_entry.pack(side=tk.LEFT, padx=5)
        
        self.load_btn = tk.Button(self.session_frame, text="Load Session", command=self.load_session)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        # Driver selection frame
        self.driver_frame = tk.Frame(root, padx=10, pady=5)
        self.driver_frame.pack(fill=tk.X)
        
        tk.Label(self.driver_frame, text="Select Driver:").pack(side=tk.LEFT)
        self.driver_var = tk.StringVar()
        self.driver_dropdown = ttk.Combobox(self.driver_frame, textvariable=self.driver_var, state="disabled")
        self.driver_dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.driver_dropdown.bind("<<ComboboxSelected>>", self.update_lap_times)
        
        # Table frame
        self.table_frame = tk.Frame(root)
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview (table)
        self.tree = ttk.Treeview(self.table_frame)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbars
        y_scroll = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll = ttk.Scrollbar(self.tree, orient="horizontal", command=self.tree.xview)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Initialize data storage
        self.session_info = None
        self.drivers = []
        self.lap_times = pd.DataFrame()
        
        # Set status
        self.status_var.set("Ready. Enter a session key and click 'Load Session'")
    
    def load_session(self):
        session_key = self.session_entry.get().strip()
        if not session_key:
            messagebox.showerror("Error", "Please enter a session key")
            return
        
        try:
            session_key = int(session_key)
        except ValueError:
            messagebox.showerror("Error", "Session key must be a number")
            return
        
        self.status_var.set(f"Loading session {session_key}...")
        self.root.update()
        
        # Get session info
        try:
            session_info = self.get_session_info(session_key)
            if not session_info:
                messagebox.showerror("Error", f"No session found with key {session_key}")
                self.status_var.set("Ready")
                return
                
            self.session_info = session_info
            session_name = f"{session_info.get('meeting_name', 'Unknown')} - {session_info.get('session_name', 'Unknown')}"
            self.root.title(f"F1 Lap Times Viewer - {session_name}")
            
            # Get drivers
            self.drivers = self.get_drivers(session_key)
            if not self.drivers:
                messagebox.showerror("Error", f"No drivers found for session {session_key}")
                self.status_var.set("Ready")
                return
                
            # Update driver dropdown
            driver_options = []
            driver_dict = {}
            for driver in self.drivers:
                name = driver.get('broadcast_name', f"Driver {driver.get('driver_number')}")
                team = driver.get('team_name', 'Unknown')
                driver_str = f"{driver['driver_number']}: {name} ({team})"
                driver_options.append(driver_str)
                driver_dict[driver_str] = driver['driver_number']
            
            self.driver_options = driver_options
            self.driver_dict = driver_dict
            self.driver_dropdown['values'] = driver_options
            self.driver_dropdown['state'] = 'readonly'
            
            # Load all lap times
            self.status_var.set(f"Loading lap times for session {session_key}...")
            self.root.update()
            self.lap_times = self.get_lap_times(session_key)
            
            if self.lap_times.empty:
                messagebox.showwarning("Warning", "No lap times found for this session")
                self.status_var.set("Ready")
                return
                
            # Select first driver by default
            if driver_options:
                self.driver_var.set(driver_options[0])
                self.update_lap_times()
                
            self.status_var.set(f"Loaded session {session_key} - {session_name}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
            self.status_var.set("Ready")
    
    def get_session_info(self, session_key):
        try:
            url = "https://api.openf1.org/v1/sessions"
            response = requests.get(url)
            sessions = response.json()
            
            # Filter sessions locally to find matching session_key
            matching_sessions = [s for s in sessions if s.get('session_key') == session_key]
            
            if not matching_sessions:
                return None
                
            return matching_sessions[0]
        except Exception as e:
            print(f"Error fetching session info: {e}")
            return None
    
    def get_drivers(self, session_key):
        url = "https://api.openf1.org/v1/drivers"
        params = {"session_key": session_key}
        response = requests.get(url, params=params)
        drivers = response.json()
        
        # Remove duplicates by driver number
        unique_drivers = {}
        for driver in drivers:
            if 'driver_number' in driver:
                unique_drivers[driver['driver_number']] = driver
        return list(unique_drivers.values())
    
    def get_lap_times(self, session_key):
        all_laps = []
        
        for driver in self.drivers:
            driver_number = driver['driver_number']
            url = "https://api.openf1.org/v1/laps"
            params = {
                "session_key": session_key,
                "driver_number": driver_number
            }
            response = requests.get(url, params=params)
            laps = response.json()
            
            if laps:
                df = pd.DataFrame(laps)
                df['driver_number'] = driver_number
                
                # Convert lap_duration to formatted time if it exists
                if 'lap_duration' in df.columns:
                    df['formatted_lap_time'] = df['lap_duration'].apply(self.format_lap_time)
                
                all_laps.append(df)
        
        if not all_laps:
            return pd.DataFrame()
            
        full_df = pd.concat(all_laps, ignore_index=True)
        
        # Select relevant columns - include both original and formatted time
        columns_to_show = ["driver_number", "lap_number", "lap_duration", "formatted_lap_time",
                         "stint_number", "compound", "is_pit_out_lap", "is_pit_in_lap", "is_valid"]
        available_columns = [col for col in columns_to_show if col in full_df.columns]
        full_df = full_df[available_columns]
        
        return full_df.sort_values(["driver_number", "lap_number"])
    
    def format_lap_time(self, seconds):
        """Convert seconds to minutes:seconds.milliseconds format"""
        if pd.isna(seconds):
            return "N/A"
        
        try:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}:{remaining_seconds:06.3f}"
        except (TypeError, ValueError):
            return str(seconds)
    
    def update_lap_times(self, event=None):
        selected_driver = self.driver_var.get()
        if not selected_driver or self.lap_times.empty:
            return
            
        driver_number = self.driver_dict[selected_driver]
        driver_laps = self.lap_times[self.lap_times['driver_number'] == driver_number]
        
        # Clear existing table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Set up columns - use formatted time instead of raw seconds
        columns_to_display = [col for col in driver_laps.columns if col != 'lap_duration']
        self.tree['columns'] = columns_to_display
        self.tree.column("#0", width=0, stretch=tk.NO)
        
        # Configure column headings and widths
        col_widths = {
            'driver_number': 50,
            'lap_number': 50,
            'formatted_lap_time': 100,
            'stint_number': 50,
            'compound': 70,
            'is_pit_out_lap': 80,
            'is_pit_in_lap': 80,
            'is_valid': 60
        }
        
        for col in columns_to_display:
            width = col_widths.get(col, 100)
            self.tree.column(col, anchor=tk.CENTER, width=width)
            self.tree.heading(col, text=col.replace('_', ' ').title())
        
        # Add data to table
        for _, row in driver_laps.iterrows():
            # Replace raw lap_duration with formatted time in display
            values = []
            for col in columns_to_display:
                if col == 'formatted_lap_time' and pd.isna(row.get('lap_duration')):
                    values.append("N/A")
                else:
                    values.append(row[col])
            
            self.tree.insert("", tk.END, values=values)
        
        self.status_var.set(f"Showing lap times for {selected_driver}")

def main():
    root = tk.Tk()
    app = F1LapTimesApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()