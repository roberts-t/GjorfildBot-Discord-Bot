import spotipy
import config.config as config
import datetime
from spotipy.oauth2 import SpotifyOAuth
from logger.CustomLog import Log


class SpotifyAPI:
    def __init__(self, scope: str = None, logger: Log = None):
        self.client_id = config.spotify_client_id
        self.client_secret = config.spotify_client_secret
        self.scope = scope
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyOAuth(scope=None, open_browser=False, client_id=self.client_id,
                                      client_secret=self.client_secret, redirect_uri="http://localhost:8080"))
        self.log = logger

    def get_spotify_playlist(self, playlist_url):
        try:
            playlist = []
            playlist_id = self.get_id_from_url(playlist_url)
            self.log.log_music(self.log.LOG_TYPE_INFO, 'get_spotify_playlist',
                               'Playlist id retrieved: ' + str(playlist_id))
            if playlist_id != '':
                playlist_info = self.spotify.playlist(str(playlist_id),
                                                      fields="tracks.items.track.name, "
                                                             "tracks.items.track.duration_ms, "
                                                             "tracks.items.track.external_urls, "
                                                             "tracks.items.track.album.name, "
                                                             "tracks.items.track.album.artists")
                self.log.log_music(self.log.LOG_TYPE_INFO, 'get_spotify_playlist',
                                   'Playlist info retrieved: ' + str(playlist_info)[:255])
                for track in playlist_info['tracks']['items']:
                    track = self.__get_track_data(track['track'])
                    playlist.append(track)

                self.log.log_music(self.log.LOG_TYPE_INFO, 'get_spotify_playlist',
                                   'Found tracks: ' + str(playlist)[:50])
            return playlist
        except Exception as e:
            self.log.log_music(self.log.LOG_TYPE_ERROR, 'get_spotify_playlist', str(e))
        return []

    def get_spotify_track(self, track_url):
        try:
            track_id = self.get_id_from_url(track_url)
            self.log.log_music(self.log.LOG_TYPE_INFO, 'get_track_title', 'Track id retrieved: ' + str(track_id))
            if track_id != '':
                track_info = self.spotify.track(str(track_id))
                self.log.log_music(self.log.LOG_TYPE_INFO, 'get_track_title',
                                   'Track info retrieved: ' + str(track_info)[:255])

                track = self.__get_track_data(track_info)
                self.log.log_music(self.log.LOG_TYPE_INFO, 'get_spotify_track', 'Track info: ' + str(track))
                return track
            return []
        except Exception as e:
            self.log.log_music(self.log.LOG_TYPE_ERROR, 'get_spotify_track', str(e))
        return []

    def __get_track_data(self, track):
        try:
            artists = ""
            for artist in track['album']['artists']:
                artists += artist['name'] + ", "

            if track['name'] is not None and track['album']['name'] != track['name']:
                title = track['album']['name'] + " - " + track['name'] + " - " + artists[:-2]
            else:
                title = track['album']['name'] + " - " + artists[:-2]

            duration = datetime.datetime.fromtimestamp(track['duration_ms'] / 1000.0).strftime('%M:%S')
            spotify_url = track['external_urls']['spotify']

            track = {
                'title': title,
                'artists': artists[:-2],
                'duration': duration,
                'url': spotify_url,
            }
            return track
        except Exception as e:
            self.log.log_music(self.log.LOG_TYPE_ERROR, 'get_track_data(spotify)', str(e))
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
