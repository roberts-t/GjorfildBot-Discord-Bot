from enum import Enum


class AudioType(Enum):
    Spotify_Track = "spotify-track"
    Spotify_Playlist = "spotify-playlist"
    Youtube_Track = "youtube-track"
    Youtube_Playlist = "youtube-playlist"
    Search = "search"
    Unknown = "unknown"
