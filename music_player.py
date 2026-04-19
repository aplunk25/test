import os
import random
import pygame

MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photontracks")

last_track_idx = -1

pygame.mixer.init()

def get_tracks():
    tracks = []
    for f in os.listdir(MUSIC_DIR):
        if f.endswith(".mp3"):
            tracks.append(os.path.join(MUSIC_DIR, f))
    return tracks

def play_music():
    global last_track_idx
    tracks = get_tracks()

    if not tracks:
        return

    choices = [i for i in range(len(tracks)) if i != last_track_idx]
    idx = random.choice(choices)
    last_track_idx = idx

    pygame.mixer.music.load(tracks[idx])
    pygame.mixer.music.play()
