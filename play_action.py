#!/usr/bin/env python3
"""
Play Action Display - Live Game Screen for Photon Laser Tag
Shows: team scores, player leaderboard, hit notifications, game timer.
Listens on UDP port 7501 for hit codes (format: "shooter_id:target_id").
Also polls PostgreSQL for player codenames.
"""

import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk
import socket
import threading
import queue
import psycopg2
from psycopg2 import sql
from typing import Optional
from UDP_Client import send_packet

# UDP listener config
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 7502          # port that server broadcasts to
BUFFER_SIZE = 1024

# Game settings
GAME_DURATION_SECONDS = 360   # 6-minute game
HIT_SCORE = 10    # points per hit
BASE_SCORE = 100
BASE_IDS = {"53", "43"}  # 43 = red base, 53 = green base


BG = "#0a0a12"
PANEL_BG = "#10101e"
RED_COLOR = "#ff2244"
GREEN_COLOR = "#00ff88"
GOLD = "#ffd700"
WHITE = "#f0f0ff"
GREY = "#44445a"
CYAN = "#00d4ff"

TEAM_COLORS = ["#ff2244", "#00ff88"]   # red, green
TEAM_NAMES = ["RED TEAM", "GREEN TEAM"]


class PlayActionDisplay:
    """Full-screen play-action scoreboard launched after countdown ends."""

    def __init__(self, parent, pg_config: dict, game_seconds: int = GAME_DURATION_SECONDS):
        self.pg_config = dict(pg_config)

        # State
        # players[team_idx] = { equipment_id: {"codename": str, "score": int, "hits": int} }
        self.players: list[dict] = [{}, {}]
        self._load_players_from_db()

        self.team_scores = [0, 0]
        self.time_left = game_seconds
        self.running = True
        self.hit_feed: list[str] = []   # recent hit messages
        self.MAX_FEED = 8
        self.base_capturers: set = set()  # tracks player IDs who hit base

        self._event_queue: queue.Queue = queue.Queue()

        # Window
        self.root = tk.Toplevel(parent)
        self.root.title("PHOTON")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)

        self._build_fonts()

        # Load base icon
        try:
            img = Image.open("baseicon.jpg").resize((16, 16), Image.LANCZOS)
            self.base_icon = ImageTk.PhotoImage(img)
        except Exception:
            self.base_icon = None

        self._build_ui()

        # Background threads
        self._udp_thread = threading.Thread(
            target=self._udp_listener, daemon=True)
        self._udp_thread.start()

        self._refresh_ui()   # populate leaderboards immediately on open
        self._poll_queue()  # drain event queue safely on main thread
        self._tick()        # start 1-second timer

    # DB helpers

    def _load_players_from_db(self):
        """Load all players from DB using the saved team column (0=red, 1=green)."""
        try:
            with psycopg2.connect(**self.pg_config) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, codename FROM players ORDER BY id;")
                    rows = cur.fetchall()

            for pid, codename in rows:
                team_idx = 0 if str(pid) in self.players[0] else 1 
  
                self.players[team_idx][str(pid)] = {
                    "codename": codename,
                    "score":    BASE_SCORE,
                    "hits":     0,
                }
            print(
                f"[PlayAction] Loaded {len(self.players[0])} red, {len(self.players[1])} green players.")
        except Exception as e:
            print(f"[PlayAction] DB load error: {e}")

    def _get_codename(self, equipment_id: str) -> str:
        for team in self.players:
            if equipment_id in team:
                return team[equipment_id]["codename"]
        return f"ID#{equipment_id}"

    def _get_team_of(self, equipment_id: str) -> Optional[int]:
        for idx, team in enumerate(self.players):
            if equipment_id in team:
                return idx
        return None

    # UDP listener (runs in background thread)

    def _udp_listener(self):
        """
        Expected packet formats:
          "shooter_id:target_id"   → hit event
          "202"                    → start signal (already consumed by countdown; ignored here)
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        try:
            sock.bind((LISTEN_IP, LISTEN_PORT))
        except OSError as e:
            print(f"[PlayAction] UDP bind error: {e}")
            return

        while self.running:
            try:
                data, _ = sock.recvfrom(BUFFER_SIZE)
                msg = data.decode().strip()
                self._process_udp(msg)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[PlayAction] UDP error: {e}")

        sock.close()

    def _process_udp(self, msg: str):
        """Parse a hit packet and update scores."""
        if ":" not in msg:
            return   # not a hit packet
        parts = msg.split(":")
        if len(parts) != 2:
            return

        shooter_id, target_id = parts[0].strip(), parts[1].strip()

        shooter_team = self._get_team_of(shooter_id)

        if shooter_team is None:
            return

        # Check if target is a base
        if target_id in BASE_IDS:
            self.base_capturers.add(shooter_id)
            # bonus points for hitting base
            self.team_scores[shooter_team] += 100
            shooter_name = self._get_codename(shooter_id)
            self.hit_feed.insert(
                0, (shooter_name, "BASE", TEAM_COLORS[shooter_team]))
            if len(self.hit_feed) > self.MAX_FEED:
                self.hit_feed.pop()
            self._event_queue.put("refresh")
            return

        target_team = self._get_team_of(target_id)

        # Shooter is rewarded 100 pts for hitting opposing base
        if target_id == "53":  # Red base scored by green
            if shooter_team == 1:  # green team
                self.players[shooter_team][shooter_id]["score"] += BASE_SCORE
                self.team_scores[shooter_team] += BASE_SCORE
                self._event_queue.put("refresh")
            return

        if target_id == "43":  # Green base scored by red
            if shooter_team == 0:  # red team
                self.players[shooter_team][shooter_id]["score"] += BASE_SCORE
                self.team_scores[shooter_team] += BASE_SCORE
                self._event_queue.put("refresh")
            return

        if target_team is None:
            return

        if shooter_team == target_team:
            # Friendly fire penalty
            self.players[shooter_team][shooter_id]["score"] -= HIT_SCORE
            self.players[target_team][target_id]["score"] -= HIT_SCORE

            # Reduce team score?
            self.team_scores[shooter_team] -= HIT_SCORE * 2

            shooter_name = self._get_codename(shooter_id)
            target_name = self._get_codename(target_id)
            feed_color = TEAM_COLORS[shooter_team]

            # Add to hit feed
            self.hit_feed.insert(
                0, (shooter_name, target_name, feed_color))
            if len(self.hit_feed) > self.MAX_FEED:
                self.hit_feed.pop()

            self._event_queue.put("refresh")
            return

        # Award points
        self.players[shooter_team][shooter_id]["score"] += HIT_SCORE
        self.players[shooter_team][shooter_id]["hits"] += 1
        self.team_scores[shooter_team] += HIT_SCORE

        shooter_name = self._get_codename(shooter_id)
        target_name = self._get_codename(target_id)
        feed_color = TEAM_COLORS[shooter_team]

        self.hit_feed.insert(0, (shooter_name, target_name, feed_color))
        if len(self.hit_feed) > self.MAX_FEED:
            self.hit_feed.pop()

        # Put event on queue — never call root.after() from a worker thread on macOS
        self._event_queue.put("refresh")

    def _poll_queue(self):
        """Drain event queue on main thread every 100 ms — safe on macOS."""
        needs_refresh = False
        try:
            while True:
                self._event_queue.get_nowait()
                needs_refresh = True
        except queue.Empty:
            pass
        if needs_refresh:
            self._refresh_ui()
        if self.running:
            self.root.after(100, self._poll_queue)

    def _tick(self):
        if not self.running:
            return
        if self.time_left > 0:
            self.time_left -= 1
            self._update_timer()
            self.root.after(1000, self._tick)
        else:
            self._game_over()

    def _update_timer(self):
        mins = self.time_left // 60
        secs = self.time_left % 60
        self.timer_var.set(f"{mins:02d}:{secs:02d}")

        # Flash red in last 30 seconds
        color = RED_COLOR if self.time_left <= 30 else CYAN
        self.timer_label.configure(fg=color)

    def _build_fonts(self):
        self.font_title = tkfont.Font(family="Courier", size=22, weight="bold")
        self.font_timer = tkfont.Font(family="Courier", size=52, weight="bold")
        self.font_team = tkfont.Font(family="Courier", size=18, weight="bold")
        self.font_score = tkfont.Font(family="Courier", size=36, weight="bold")
        self.font_player = tkfont.Font(family="Courier", size=12)
        self.font_header = tkfont.Font(
            family="Courier", size=11, weight="bold")
        self.font_feed = tkfont.Font(family="Courier", size=11)
        self.font_gameover = tkfont.Font(
            family="Courier", size=48, weight="bold")

    # UI

    def _build_ui(self):
        # ── Top bar: title + timer ───────────────────────────────────────────
        top = tk.Frame(self.root, bg=PANEL_BG, pady=6)
        top.pack(fill=tk.X)

        tk.Label(top, text="PHOTON Leaderboard",
                 font=self.font_title, bg=PANEL_BG, fg=GOLD).pack()

        self.timer_var = tk.StringVar(value="06:00")
        self.timer_label = tk.Label(top, textvariable=self.timer_var,
                                    font=self.font_timer, bg=PANEL_BG, fg=CYAN)
        self.timer_label.pack()

        # Middle: team score banner
        banner = tk.Frame(self.root, bg=BG, pady=4)
        banner.pack(fill=tk.X)

        for team_idx in range(2):
            col = TEAM_COLORS[team_idx]
            f = tk.Frame(banner, bg=col, padx=20, pady=4)
            f.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

            tk.Label(f, text=TEAM_NAMES[team_idx],
                     font=self.font_team, bg=col, fg=WHITE).pack()

            score_lbl = tk.Label(f, text="0",
                                 font=self.font_score, bg=col, fg=WHITE)
            score_lbl.pack()
            if team_idx == 0:
                self.red_score_label = score_lbl
            else:
                self.green_score_label = score_lbl

        # leaderboards + hit feed
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Red leaderboard
        self.red_board_frame = self._make_leaderboard(bottom, 0)
        self.red_board_frame.pack(side=tk.LEFT, fill=tk.BOTH,
                                  expand=True, padx=(0, 4))

        # Hit feed
        feed_outer = tk.Frame(bottom, bg=PANEL_BG, bd=1, relief=tk.FLAT)
        feed_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        tk.Label(feed_outer, text="── HIT FEED ──",
                 font=self.font_header, bg=PANEL_BG, fg=GOLD).pack(pady=(6, 2))

        self.feed_frame = tk.Frame(feed_outer, bg=PANEL_BG)
        self.feed_frame.pack(fill=tk.BOTH, expand=True, padx=6)

        self.feed_labels: list[tk.Label] = []
        for _ in range(self.MAX_FEED):
            lbl = tk.Label(self.feed_frame, text="",
                           font=self.font_feed, bg=PANEL_BG,
                           fg=GREY, anchor=tk.W, justify=tk.LEFT)
            lbl.pack(fill=tk.X, pady=1)
            self.feed_labels.append(lbl)

        # Green leaderboard
        self.green_board_frame = self._make_leaderboard(bottom, 1)
        self.green_board_frame.pack(side=tk.LEFT, fill=tk.BOTH,
                                    expand=True, padx=(4, 0))

        # ESC or F5 → close play action and return to player entry
        self.root.bind("<Escape>", lambda e: self._end_game())
        self.root.bind("<F5>", lambda e: self._end_game())

    def _make_leaderboard(self, parent, team_idx: int) -> tk.Frame:
        color = TEAM_COLORS[team_idx]
        outer = tk.Frame(parent, bg=PANEL_BG, bd=1, relief=tk.FLAT)

        tk.Label(outer,
                 text=f"── {TEAM_NAMES[team_idx]} LEADERBOARD ──",
                 font=self.font_header, bg=PANEL_BG, fg=color).pack(pady=(6, 2))

        # Column headers
        hdr = tk.Frame(outer, bg=PANEL_BG)
        hdr.pack(fill=tk.X, padx=6)
        tk.Label(hdr, text="#",      width=3,  font=self.font_header,
                 bg=PANEL_BG, fg=GREY).pack(side=tk.LEFT)
        tk.Label(hdr, text="CODENAME", width=16, font=self.font_header,
                 bg=PANEL_BG, fg=GREY, anchor=tk.W).pack(side=tk.LEFT)
        tk.Label(hdr, text="SCORE",  width=7,  font=self.font_header,
                 bg=PANEL_BG, fg=GREY).pack(side=tk.LEFT)
        tk.Label(hdr, text="HITS",   width=5,  font=self.font_header,
                 bg=PANEL_BG, fg=GREY).pack(side=tk.LEFT)

        # Separator
        tk.Frame(outer, bg=color, height=1).pack(fill=tk.X, padx=6, pady=2)

        rows_frame = tk.Frame(outer, bg=PANEL_BG)
        rows_frame.pack(fill=tk.BOTH, expand=True, padx=6)

        if team_idx == 0:
            self.red_rows_frame = rows_frame
        else:
            self.green_rows_frame = rows_frame

        return outer

    def _refresh_ui(self):
        self._refresh_scores()
        self._refresh_leaderboard(0)
        self._refresh_leaderboard(1)
        self._refresh_feed()

    def _refresh_scores(self):
        self.red_score_label.configure(text=str(self.team_scores[0]))
        self.green_score_label.configure(text=str(self.team_scores[1]))

    def _refresh_leaderboard(self, team_idx: int):
        frame = self.red_rows_frame if team_idx == 0 else self.green_rows_frame
        color = TEAM_COLORS[team_idx]

        # Clear existing rows
        for widget in frame.winfo_children():
            widget.destroy()

        # Sort players by score descending
        sorted_players = sorted(
            self.players[team_idx].items(),
            key=lambda kv: kv[1]["score"],
            reverse=True
        )

        for rank, (pid, data) in enumerate(sorted_players, start=1):
            row = tk.Frame(frame, bg=PANEL_BG)
            row.pack(fill=tk.X, pady=1)

            rank_color = GOLD if rank == 1 else WHITE
            fg_color = color if rank <= 3 else WHITE

            tk.Label(row, text=f"{rank}",
                     width=3, font=self.font_player,
                     bg=PANEL_BG, fg=rank_color).pack(side=tk.LEFT)
            tk.Label(row, text=data["codename"][:14],
                     width=16, font=self.font_player,
                     bg=PANEL_BG, fg=fg_color, anchor=tk.W).pack(side=tk.LEFT)

            # Show base icon if this player has hit base
            if pid in self.base_capturers and self.base_icon:
                tk.Label(row, image=self.base_icon,
                         bg=PANEL_BG).pack(side=tk.LEFT)

            tk.Label(row, text=str(data["score"]),
                     width=7, font=self.font_player,
                     bg=PANEL_BG, fg=fg_color).pack(side=tk.LEFT)
            tk.Label(row, text=str(data["hits"]),
                     width=5, font=self.font_player,
                     bg=PANEL_BG, fg=GREY).pack(side=tk.LEFT)

    def _refresh_feed(self):
        for i, lbl in enumerate(self.feed_labels):
            if i < len(self.hit_feed):
                shooter, target, color = self.hit_feed[i]
                if target == "BASE":
                    lbl.configure(
                        text=f"  {shooter} → hit → BASE 🏠",
                        fg=color
                    )
                else:
                    lbl.configure(
                        text=f"  {shooter} → tagged → {target}",
                        fg=color
                    )
            else:
                lbl.configure(text="", fg=GREY)

    # Game over

    def _game_over(self):
        self.running = False
        red_score = self.team_scores[0]
        green_score = self.team_scores[1]

        if red_score > green_score:
            winner, win_color = "RED TEAM WINS!", RED_COLOR
        elif green_score > red_score:
            winner, win_color = "GREEN TEAM WINS!", GREEN_COLOR
        else:
            winner, win_color = "IT'S A TIE!", GOLD

        overlay = tk.Frame(self.root, bg=BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        tk.Label(overlay, text="GAME OVER",
                 font=self.font_gameover, bg=BG, fg=GOLD).pack(pady=(120, 10))
        tk.Label(overlay, text=winner,
                 font=self.font_gameover, bg=BG, fg=win_color).pack()
        tk.Label(overlay,
                 text=f"RED  {red_score}   |   GREEN  {green_score}",
                 font=self.font_team, bg=BG, fg=WHITE).pack(pady=20)
        tk.Button(overlay, text="CLOSE",
                  font=self.font_team, bg=PANEL_BG, fg=WHITE,
                  activebackground=GREY, bd=0, padx=20, pady=10,
                  command=self._end_game).pack(pady=40)
        for i in range(3):
            send_packet("221")

    def _end_game(self):
        self.running = False
        self.root.destroy()


def launch_play_action(parent, pg_config: dict, game_seconds: int = GAME_DURATION_SECONDS):
    """Call this as the on_close callback of CountdownTimer."""
    PlayActionDisplay(parent, pg_config, game_seconds)


# for standalone testing
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pg_config = {"dbname": "photon", "user": "student",
                 "host": "localhost", "port": 5432}
    PlayActionDisplay(root, pg_config, game_seconds=60)
    root.mainloop()
