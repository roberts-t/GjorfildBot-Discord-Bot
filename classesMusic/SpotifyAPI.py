import spotipy
import config.config as config
from spotipy.oauth2 import SpotifyOAuth

class SpotifyAPI:
    def __init__(self, scope: str = None, logger = None):
        self.client_id = config.spotify_client_id
        self.client_secret = config.spotify_client_secret
        self.scope = scope
        self.spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=None, open_browser=False, client_id=self.client_id, client_secret=self.client_secret, redirect_uri="http://localhost:8080"))
        self.log = logger

    def get_playlist_titles(self, playlist_url: str):
        try:
            titles = []
            playlist_id = self.get_id_from_url(playlist_url)
            self.log.log_music("info", 'get_playlist_titles', 'Playlist id retrieved: ' + str(playlist_id))
            if playlist_id != '':
                playlist_info = self.spotify.playlist(str(playlist_id), fields="tracks.items.track.name, tracks.items.track.artists.name")
                self.log.log_music("info", 'get_playlist_titles', 'Playlist info retrieved: ' + str(playlist_info)[:255])
                for track in playlist_info['tracks']['items']:
                    artists = ""
                    for artist in track['track']['artists']:
                        artists += artist['name'] + ", "
                    titles.append(track['track']['name'] + " - " + artists[:-2])
                self.log.log_music("info", 'get_playlist_titles', 'Found titles: ' + str(playlist_info)[:50])
                return titles
        except Exception as e:
            self.log.log_music("error", 'get_playlist_titles', str(e))
        return []

    def get_track_title(self, track_url: str):
        try:
            track_id = self.get_id_from_url(track_url)
            self.log.log_music("info", 'get_track_title', 'Track id retrieved: ' + str(track_id))
            if track_id != '':
                track_info = self.spotify.track(str(track_id))
                self.log.log_music("info", 'get_track_title', 'Track info retrieved: ' + str(track_info)[:255])
                artists = ""
                for artist  in track_info['album']['artists']:
                    artists += artist['name'] + ", "

                if track_info['name'] is not None and track_info['album']['name'] != track_info['name']:
                    final_track_name = track_info['album']['name'] + " - " + track_info['name'] + " - " + artists[:-2]
                else:
                    final_track_name = track_info['album']['name'] + " - " + artists[:-2]

                self.log.log_music("info", 'get_track_title', 'Track info: ' + str(final_track_name))
                return final_track_name
        except Exception as e:
            self.log.log_music("error", 'get_track_title', str(e))
        return []

    def get_id_from_url(self, url: str):
        if "/playlist/" in url:
            spotify_id = url.split('playlist/', 1)
        elif "/track/" in url:
            spotify_id = url.split('track/', 1)
        else:
            return ''

        if len(spotify_id) == 2:
            spotify_id = spotify_id[1].split('?', 1)
            if len(spotify_id) == 2:
                return spotify_id[0]
            else:
                return ''
        else:
            return ''
