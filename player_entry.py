#!/usr/bin/env python3
"""
Entry Terminal - Player Entry System (Tkinter GUI)
Two teams with ID Number and Codename columns
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import psycopg2
from psycopg2 import sql
from UDP_Client import send_packet
from Countdown_timer import CountdownTimer
from play_action import launch_play_action

HARDWARE_TEAM_PAIR = {}  # Global dictionary to store hardware ID to team mapping
HARDWARE_TEAM_PAIR_FILE = "hardware_team.json"


class Team:
    def __init__(self, name: str, color: str, max_players: int = 20):
        self.name = name
        self.color = color
        # [id_number, codename] pairs
        self.players = [["", ""] for _ in range(max_players)]

    def add_player(self, index: int, id_number: str, codename: str = ""):
        if 0 <= index < len(self.players):
            self.players[index] = [id_number, codename]

    def remove_player(self, index: int):
        if 0 <= index < len(self.players):
            self.players[index] = ["", ""]

    def get_player_count(self):
        return sum(1 for p in self.players if p[0])


class EntryTerminal:
    def __init__(self, root, pg_config):
        self.root = root
        self.root.title("Entry Terminal")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1a1a2e")
        self.hardware_id = tk.StringVar()  # store hardware ID input

        self.pg_config = dict(pg_config)   # copy from python-pg.py
        # Fill in defaults if python-pg.py omits them
        # self.pg_config.setdefault('host', 'localhost')
        # self.pg_config.setdefault('port', 5432)
        self.table_name = "players"
        self.id_column = "id"
        self.codename_column = "codename"
        self._ensure_table()

        # Teams
        self.teams = [
            Team("RED TEAM", "#8B0000", 20),
            Team("GREEN TEAM", "#006400", 20)
        ]

        # Current selection
        self.current_team = 0
        self.current_slot = 0
        self.current_column = 0

        # Game mode
        self.game_mode = "Standard public mode"

        # Entry widgets storage
        # team_idx -> list of (id_entry, codename_entry, row_frame)
        self.entry_widgets = {0: [], 1: []}

        self.create_ui()

    def _ensure_table(self):
        """Create the players table if it doesn't exist."""
        try:
            with psycopg2.connect(**self.pg_config) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS players (
                            id INTEGER PRIMARY KEY,
                            codename TEXT NOT NULL
                        );
                    """)
                    
                conn.commit()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def _db_upsert(self, pid: int, codename: str, team: int = 0):
        with psycopg2.connect(**self.pg_config) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO players (id, codename) VALUES (%s, %s);",
                    (pid, codename)
                )
            conn.commit()

    def _db_delete(self, pid: int):
        """Delete a player row by id."""
        q = sql.SQL("DELETE FROM {t} WHERE {idc} = %s;").format(
            t=sql.Identifier(self.table_name),
            idc=sql.Identifier(self.id_column),
        )
        with psycopg2.connect(**self.pg_config) as conn:
            with conn.cursor() as cur:
                cur.execute(q, (pid,))
            conn.commit()

    def save_row(self, team_idx: int, slot_idx: int):
        """Save (upsert) a single UI row to Postgres after typing."""
        try:
            id_entry, codename_entry, _, checkbox_var = self.entry_widgets[team_idx][slot_idx]
        except Exception:
            return

        id_str = id_entry.get().strip()
        code = codename_entry.get().strip()

        # Nothing to save
        if not id_str and not code:
            checkbox_var.set(False)
            return

        if not id_str.isdigit():
            messagebox.showerror(
                "Input Error", "Equipment ID must be numeric.")
            return

        pid = int(id_str)

        # If codename empty, try to look it up (optional convenience)
        if not code:
            code = self.lookup_codename(id_str).strip()
            if code:
                codename_entry.delete(0, tk.END)
                codename_entry.insert(0, code)

        if not code:
            # still empty -> don't write junk row
            return

        # If both boxes are filled, prompt for hardware ID
        if checkbox_var.get() and id_str and code:
            self.create_hardware_id_popup(team_idx)

        try:
            self._db_upsert(pid, code, team_idx)
            checkbox_var.set(True)

        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def create_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#1a1a2e", height=80)
        title_frame.pack(fill=tk.X, pady=(10, 0))
        title_frame.pack_propagate(False)

        subtitle_label = tk.Label(
            title_frame,
            text="Edit Current Game",
            font=("Courier", 20, "bold"),
            bg="#1a1a2e",
            fg="#00bfff"
        )
        subtitle_label.pack()

        # Main content frame
        content_frame = tk.Frame(self.root, bg="#1a1a2e")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Create two team panels
        for team_idx in range(2):
            team_frame = tk.Frame(content_frame, bg="#1a1a2e")
            team_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

            self.create_team_panel(team_frame, team_idx)

        # Footer
        self.create_footer()

    def create_team_panel(self, parent, team_idx):
        team = self.teams[team_idx]

        # Team header
        header_frame = tk.Frame(parent, bg=team.color, height=40)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        header_label = tk.Label(
            header_frame,
            text=team.name,
            font=("Courier", 14, "bold"),
            bg=team.color,
            fg="white"
        )
        header_label.pack(expand=True)

        # Column headers
        col_header_frame = tk.Frame(parent, bg="#2a2a3e")
        col_header_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Label(
            col_header_frame,
            text="",
            width=3,
            font=("Courier", 10, "bold"),
            bg="#2a2a3e",
            fg="white"
        ).pack(side=tk.LEFT, padx=2)

        tk.Label(
            col_header_frame,
            text="ID Number",
            width=20,
            font=("Courier", 10, "bold"),
            bg="#2a2a3e",
            fg="white",
            anchor=tk.W
        ).pack(side=tk.LEFT, padx=2)

        tk.Label(
            col_header_frame,
            text="Codename",
            width=20,
            font=("Courier", 10, "bold"),
            bg="#2a2a3e",
            fg="white",
            anchor=tk.W
        ).pack(side=tk.LEFT, padx=2)

        # Scrollable roster frame
        roster_container = tk.Frame(parent, bg="#1a1a2e")
        roster_container.pack(fill=tk.BOTH, expand=True, pady=5)

        # Canvas and scrollbar
        canvas = tk.Canvas(roster_container, bg="#1a1a2e",
                           highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            roster_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1a2e")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create player rows
        for i in range(20):
            self.create_player_row(scrollable_frame, team_idx, i)

    def create_player_row(self, parent, team_idx, slot_idx):
        team = self.teams[team_idx]

        row_frame = tk.Frame(parent, bg="#2a2a3e", bd=1, relief=tk.SOLID)
        row_frame.pack(fill=tk.X, pady=1, padx=2)

        # Slot number with checkbox
        slot_frame = tk.Frame(row_frame, bg="#2a2a3e")
        slot_frame.pack(side=tk.LEFT, padx=5, pady=3)

        checkbox_var = tk.BooleanVar(value=False)
        checkbox = tk.Checkbutton(
            slot_frame,
            variable=checkbox_var,
            bg="#2a2a3e",
            fg="white",
            selectcolor="#1a1a2e",
            state=tk.DISABLED
        )
        checkbox.pack(side=tk.LEFT)

        slot_label = tk.Label(
            slot_frame,
            text=str(slot_idx),
            font=("Courier", 10),
            bg="#2a2a3e",
            fg="white",
            width=2
        )
        slot_label.pack(side=tk.LEFT)

        # ID Number entry
        id_entry = tk.Entry(
            row_frame,
            font=("Courier", 10),
            bg="#1a1a2e",
            fg="white",
            insertbackground="white",
            width=20,
            bd=0,
            highlightthickness=1,
            highlightbackground="#3a3a4e",
            highlightcolor="#00bfff"
        )
        id_entry.pack(side=tk.LEFT, padx=2, pady=2)
        id_entry.insert(0, team.players[slot_idx][0])

        # Codename entry
        codename_entry = tk.Entry(
            row_frame,
            font=("Courier", 10),
            bg="#1a1a2e",
            fg="white",
            insertbackground="white",
            width=20,
            bd=0,
            highlightthickness=1,
            highlightbackground="#3a3a4e",
            highlightcolor="#00bfff"
        )
        codename_entry.pack(side=tk.LEFT, padx=2, pady=2)
        codename_entry.insert(0, team.players[slot_idx][1])

        # Delete button
        delete_btn = tk.Button(
            row_frame,
            text="✕",
            font=("Courier", 10, "bold"),
            bg="#8B0000",
            fg="white",
            bd=0,
            padx=5,
            pady=0,
            cursor="hand2",
            command=lambda: self.delete_player(team_idx, slot_idx)
        )
        delete_btn.pack(side=tk.LEFT, padx=2)

        # Bind events for updating checkbox
        def update_checkbox(*args):
            has_data = bool(id_entry.get().strip())
            checkbox_var.set(has_data)

        id_entry.bind("<KeyRelease>", update_checkbox)
        codename_entry.bind("<KeyRelease>", update_checkbox)
        # Save to DB when user presses Enter or leaves the field
        id_entry.bind('<Return>', lambda e: self.save_row(team_idx, slot_idx))
        codename_entry.bind(
            '<Return>', lambda e: self.save_row(team_idx, slot_idx))
        # codename_entry.bind(
        # Comment out to only save data when pressing enter?
        # '<FocusOut>', lambda e: self.save_row(team_idx, slot_idx)) #Commented out to avoid prompting for hardware ID when leaving the field

        # Store references
        self.entry_widgets[team_idx].append(
            (id_entry, codename_entry, row_frame, checkbox_var))

    def delete_player(self, team_idx, slot_idx):
        if slot_idx < len(self.entry_widgets[team_idx]):
            id_entry, codename_entry, _, checkbox_var = self.entry_widgets[team_idx][slot_idx]
            id_str = id_entry.get().strip()

            # Delete from DB if an ID is present
            if id_str.isdigit():
                try:
                    self._db_delete(int(id_str))
                except Exception as e:
                    messagebox.showerror('DB Error', str(e))
                    return

            # Clear UI
            id_entry.delete(0, tk.END)
            codename_entry.delete(0, tk.END)
            checkbox_var.set(False)

    def create_footer(self):
        footer_frame = tk.Frame(self.root, bg="#1a1a2e", height=120)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        footer_frame.pack_propagate(False)

        # Game mode
        mode_label = tk.Label(
            footer_frame,
            text=f"Game Mode: {self.game_mode}",
            font=("Courier", 11),
            bg="#1a1a2e",
            fg="white"
        )
        mode_label.pack(pady=(5, 10))

        # Function buttons frame
        buttons_frame = tk.Frame(footer_frame, bg="#1a1a2e")
        buttons_frame.pack()

        functions = [
            ("F1\nEdit Game", self.edit_game),
            ("F2\nGame\nParameters", self.game_parameters),
            ("F3\nPreEntered\nGames", self.preentered_games),
            ("F5\nStart\nGames", self.start_games),
            ("F7\n\n", None),
            ("F8\nView\nGame", self.view_game),
            ("F10\nFlick\nSync", self.flick_sync),
            ("F12\nClear\nGame", self.clear_game)
        ]

        for label, command in functions:
            btn = tk.Button(
                buttons_frame,
                text=label,
                font=("Courier", 8),
                bg="#2a2a3e",
                fg="white",
                activebackground="#3a3a4e",
                activeforeground="white",
                bd=1,
                relief=tk.RAISED,
                width=10,
                height=3,
                command=command if command else lambda: None
            )
            btn.pack(side=tk.LEFT, padx=5)

        # Instructions
        instructions = tk.Label(
            footer_frame,
            text="<Del> to Delete Player, <Ins> to Manually Insert, or edit codename",
            font=("Courier", 9),
            bg="#1a1a2e",
            fg="#888888"
        )
        instructions.pack(pady=(10, 0))

        # Bind keyboard shortcuts
        self.root.bind("<F1>", lambda e: self.edit_game())
        self.root.bind("<F2>", lambda e: self.game_parameters())
        self.root.bind("<F3>", lambda e: self.preentered_games())
        self.root.bind("<F5>", lambda e: self.start_games())
        self.root.bind("<F8>", lambda e: self.view_game())
        self.root.bind("<F10>", lambda e: self.flick_sync())
        self.root.bind("<F12>", lambda e: self.clear_game())

    def get_all_players(self):
        """Get all players from both teams"""
        all_players = {"red_team": [], "green_team": []}

        for team_idx, team_key in enumerate(["red_team", "green_team"]):
            for id_entry, codename_entry, _, _ in self.entry_widgets[team_idx]:
                id_num = id_entry.get().strip()
                codename = codename_entry.get().strip()
                if id_num or codename:
                    all_players[team_key].append({
                        "id_number": id_num,
                        "codename": codename
                    })

        return all_players

    def edit_game(self):
        messagebox.showinfo("Edit Game", "Edit Game function")

    def game_parameters(self):
        messagebox.showinfo("Game Parameters", "Game Parameters function")

    def start_games(self):
        players = self.get_all_players()
        red_count = len(players["red_team"])
        green_count = len(players["green_team"])

        msg = f"Starting game with:\nRed Team: {red_count} players\nGreen Team: {green_count} players"
        messagebox.showinfo("Start Games", msg)

        # Start countdown; when it finishes, launch the Play Action display
        def _after_countdown():
            # Close player entry screen
            # `self.root.destroy()`
            launch_play_action(self.root, self.pg_config)

        CountdownTimer(self.root, on_close=_after_countdown,
                       image_path="countdown_images", seconds=30)

    def preentered_games(self):
        messagebox.showinfo("PreEntered Games", "PreEntered Games function")

    def view_game(self):
        players = self.get_all_players()
        msg = f"Red Team Players: {len(players['red_team'])}\n"
        msg += f"Green Team Players: {len(players['green_team'])}"
        messagebox.showinfo("View Game", msg)

    def flick_sync(self):
        messagebox.showinfo("Flick Sync", "Flick Sync function")

    def clear_game(self):
        result = messagebox.askyesno(
            "Clear Game",
            "Are you sure you want to clear all players?"
        )
        if result:
            try:
                with psycopg2.connect(**self.pg_config) as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM players;")
                    conn.commit()
            except Exception as e:
                messagebox.showerror("DB Error", str(e))
                return
            for team_idx in range(2):
                for id_entry, codename_entry, _, checkbox_var in self.entry_widgets[team_idx]:
                    id_entry.delete(0, tk.END)
                    codename_entry.delete(0, tk.END)
                    checkbox_var.set(False)

    def lookup_codename(self, id_number: str) -> str:
        if not id_number.strip():
            return ""
        query = sql.SQL("SELECT {codename_col} FROM {table} WHERE {id_col} = %s LIMIT 1").format(
            codename_col=sql.Identifier(self.codename_column),
            table=sql.Identifier(self.table_name),
            id_col=sql.Identifier(self.id_column),
        )
        try:
            with psycopg2.connect(**self.pg_config) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (id_number.strip(),))
                    row = cur.fetchone()
                    return row[0] if row else ""
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return ""
    # Save the current hardware-team mapping to JSON

    def save_hardware_team_pair(self):
        HARDWARE_TEAM_PAIR_FILE = "hardware_team.json"
        try:
            with open(HARDWARE_TEAM_PAIR_FILE, "w") as f:
                json.dump(HARDWARE_TEAM_PAIR, f)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # Load hardware-team mapping from JSON
    def load_hardware_team_pair(self):
        HARDWARE_TEAM_PAIR_FILE = "hardware_team.json"
        try:
            if os.path.exists(HARDWARE_TEAM_PAIR_FILE):
                with open(HARDWARE_TEAM_PAIR_FILE, "r") as f:
                    global HARDWARE_TEAM_PAIR  # Use global to modify the global variable
                    HARDWARE_TEAM_PAIR = json.load(f)
            else:
                print("No saved JSON file found.")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    # Get hardware ID and error handling
    def get_hardware_id(self):
        h_str = self.hardware_id.get().strip()
        if not h_str:
            messagebox.showerror(
                "Invalid Input", "Hardware ID cannot be empty.")
            return None
        if not h_str.isdigit():
            messagebox.showerror(
                "Invalid Input", "Hardware ID must be a number.")
            return None
        return int(h_str)

   # Function to grab hardware ID and send it back to server
    def send_hardware_id(self, popup, team_idx):
        h_id = self.get_hardware_id()
        if h_id is None:
            return

        # Call create_hardware_team_pair here to ensure the mapping is created before sending the packet
        self.create_hardware_team_pair(h_id, team_idx)
        # h_id = int(h_id_str)
        send_packet(h_id)
        popup.destroy()

    # Function to create key-value pair for hardware_id and Team
    def create_hardware_team_pair(self, h_id, team_idx):
        # h_id = self.get_hardware_id() This tries to read hardware before the user has a chance to input it.
        if (team_idx == 0):
            HARDWARE_TEAM_PAIR[h_id] = "RED"
        elif (team_idx == 1):
            HARDWARE_TEAM_PAIR[h_id] = "GREEN"
        # Save the updated mapping to JSON after adding a new pair!
        self.save_hardware_team_pair()

    # Function to create a pop up for hardware ID

    def create_hardware_id_popup(self, team_idx):
        # Sets hardware_id to empty to ensure the field is blank
        self.hardware_id.set("")
        # Creates a popup
        popup = tk.Toplevel(self.root)
        popup.title("Hardware ID Input")
        popup.geometry("300x150")

        popup.transient(self.root)   # associate with parent
        popup.grab_set()             # make it modal (blocks interaction behind)
        popup.focus_force()          # force focus
        popup.lift()                 # bring to front

        # Creates a frame to hold the widgets
        frame = tk.Frame(popup)
        frame.pack(pady=20)  # Center frame in y axis

        # Create input field for ID
        hardware_id_label = tk.Label(
            frame, text="Enter Hardware ID: ")  # Label for input field
        hardware_id_entry = tk.Entry(
            # Input field
            frame, textvariable=self.hardware_id)

        # Create a button to submit ID
        # Button calls function when submitting
        submit_button = tk.Button(
            frame, text="Submit", command=lambda: self.send_hardware_id(popup, team_idx))

        # Place widgets on the window
        hardware_id_label.grid(row=0, column=0)
        hardware_id_entry.grid(row=0, column=1)
        submit_button.grid(row=1, column=0, columnspan=2, pady=10)

        # Binds enter key to submit button
        hardware_id_entry.bind(
            "<Return>",
            lambda e: self.send_hardware_id(popup, team_idx)
        )


def entry_terminal(root_or_config, pg_config=None):
    if pg_config is None:
        # Called old way from python-pg.py: entry_terminal(connection_params)
        pg_config = root_or_config
        root = tk.Tk()
        app = EntryTerminal(root, pg_config)
        root.mainloop()
    else:
        # Called new way: entry_terminal(root, pg_config)
        root = root_or_config
        win = tk.Toplevel(root)
        app = EntryTerminal(win, pg_config)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    entry_terminal(root, {"dbname": "photon", "user": "student",
                          "host": "localhost", "port": 5432})
    root.mainloop()
