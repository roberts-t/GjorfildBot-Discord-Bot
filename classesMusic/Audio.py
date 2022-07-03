import yt_dlp
from logger.CustomLog import Log
from classesMusic.AudioType import AudioType


class Audio:
    def __init__(self, ydl_options: dict, source_url: str, perform_search: bool, audio_type: AudioType, duration: str,
                 title: str = None, logger: Log = None):
        self.title = title
        self.duration = duration
        self.output_url = None
        self.thumbnail = None
        self.source_url = source_url
        self.audio_type = audio_type
        self.perform_search = perform_search
        self.log = logger
        self.options = ydl_options

    def play(self):
        try:
            if self.perform_search:
                self.search()
            else:
                yt_downloader = yt_dlp.YoutubeDL(self.options)
                yt_info = yt_downloader.extract_info(self.source_url, download=False)
                self.get_youtube_data(yt_info)
            return self.output_url

        except Exception as e:
            self.log.log_music(self.log.LOG_TYPE_ERROR, 'play', str(e))
            return None

    def search(self):
        yt_downloader = yt_dlp.YoutubeDL(self.options)
        yt_info = yt_downloader.extract_info(f"ytsearch1:{self.title}", download=False)
        if yt_info['entries'] and len(yt_info['entries']) > 0:
            info = yt_info['entries'][0]
            self.get_youtube_data(info)

    def get_youtube_data(self, yt_info):
        duration = yt_info.get('duration_string')
        try:
            thumbnail = yt_info.get('thumbnails')[0]['url']
            self.thumbnail = thumbnail
        except Exception as e:
            self.log.log_music(self.log.LOG_TYPE_ERROR, "get_youtube_data",
                               "Failed to find thumbnail for: " + self.title)
        if duration is not None:
            self.duration = yt_info.get('duration_string')
        self.output_url = yt_info.get('url')
