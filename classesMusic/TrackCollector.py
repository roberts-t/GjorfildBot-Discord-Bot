import re
from classesMusic.SpotifyAPI import SpotifyAPI
from classesMusic.Audio import Audio
from classesMusic.AudioType import AudioType
import datetime
import yt_dlp


class TrackCollector:

    def __init__(self, logger):
        self.url_regex = re.compile(
            r'^(?:http|ftp)s?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        self.options = {'format': 'bestaudio/best',
                        'exctractaudio': True,
                        'nocheckcertificate': True,
                        'ignoreerrors': False,
                        'quiet': True,
                        'noplaylist': True,
                        'logtostderr': False,
                        'no_warnings': True,
                        'restrictfilenames': True,
                        'default_search': 'auto',
                        'source_address': '0.0.0.0'}
        self.spotify = SpotifyAPI(logger=logger)
        self.logger = logger

    def __get_audio_source_type(self, audio_source):
        if not re.match(self.url_regex, audio_source):
            return AudioType.Search
        else:
            if "spotify" in audio_source:
                if "/track/" in audio_source:
                    return AudioType.Spotify_Track
                elif "/playlist/" in audio_source:
                    return AudioType.Spotify_Playlist
            elif "youtube" in audio_source or "youtu.be" in audio_source:
                if "playlist" in audio_source or "list" in audio_source:
                    return AudioType.Youtube_Playlist
                return AudioType.Youtube_Track
        return AudioType.Unknown

    def get_audio_data(self, audio_source):
        audio_type = self.__get_audio_source_type(audio_source)

        if audio_type == AudioType.Spotify_Track:
            track = self.spotify.get_spotify_track(audio_source)
            if len(track) > 0:
                return [Audio(self.options, audio_source, True, audio_type, track['duration'], track['title'])]

        elif audio_type == AudioType.Spotify_Playlist:
            playlist = []
            tracks = self.spotify.get_spotify_playlist(audio_source)
            if len(tracks) > 0:
                for track in tracks:
                    audio = Audio(self.options, track['url'], True, audio_type, track['duration'], track['title'])
                    playlist.append(audio)
                return playlist

        elif audio_type == AudioType.Youtube_Track:
            yt_downloader = yt_dlp.YoutubeDL(self.options)
            yt_info = yt_downloader.extract_info(audio_source, download=False)
            return [Audio(self.options, audio_source, False, audio_type, yt_info['duration_string'], yt_info['title'])]

        elif audio_type == AudioType.Youtube_Playlist:
            audio_playlist = []
            dl_options = dict(self.options)
            dl_options['playlist_flat'] = True
            dl_options['extract_flat'] = True
            yt_downloader = yt_dlp.YoutubeDL(dl_options)
            yt_info = yt_downloader.extract_info(audio_source, download=False)
            for info in yt_info['entries']:
                # Check for private or deleted video
                if info['duration'] is not None:
                    duration = datetime.datetime.fromtimestamp(info['duration']).strftime('%M:%S')
                    audio = Audio(self.options, info['url'], False, audio_type, duration, info['title'])
                    audio_playlist.append(audio)
            return audio_playlist

        elif audio_type == AudioType.Search:
            dl_options = dict(self.options)
            dl_options['playlist_flat'] = True
            dl_options['extract_flat'] = True
            yt_downloader = yt_dlp.YoutubeDL(self.options)
            yt_info = yt_downloader.extract_info(f"ytsearch1:{audio_source}", download=False)
            yt_info = yt_info['entries'][0]
            duration = datetime.datetime.fromtimestamp(yt_info['duration']).strftime('%M:%S')
            return [Audio(self.options, yt_info['webpage_url'], False, audio_type, duration, yt_info['title'])]

