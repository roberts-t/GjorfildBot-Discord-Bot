import yt_dlp

class Audio:
    def __init__(self, url: str, is_search: bool, title: str = None, logger = None):
        self.id = None
        self.title = title
        self.info = None
        self.yt_info = None
        self.play_url = None
        self.url = url
        self.is_search = is_search
        self.log = logger


    def get_url(self):
        return self.url

    def get_play_url(self):
        return self.play_url

    def get_title(self):
        return self.title

    def get_id(self):
        return self.id

    def retrieve_audio_data(self, YDL_OPTIONS):
        try:
            yt_downloader = yt_dlp.YoutubeDL(YDL_OPTIONS)
            if self.is_search:
                self.yt_info = yt_downloader.extract_info(f"ytsearch:{self.url}", download=False)
            else:
                self.yt_info = yt_downloader.extract_info(self.url, download=False)
            yt_downloader.sanitize_info(self.yt_info)
            if self.is_search:
                # Get first result
                if 'entries' in self.yt_info:
                    self.title = self.yt_info['entries'][0]['title']
                    self.info = self.yt_info['entries'][0]
                    self.id = self.yt_info['entries'][0]['id']
                    self.url = self.yt_info['entries'][0]['webpage_url']
                elif 'formats' in self.yt_info:
                    self.info = self.yt_info["formats"][0]
            else:
                self.title = self.yt_info['title']
                self.info = self.yt_info
                self.id = self.info['id']
            self.play_url = self.info['url']
            self.log.log_music("info", 'retrieve_audio_data', 'Audio data retrieved: ' + str(self.title) + ' | ' + str(self.id) + ' | ' + str(self.play_url))
        except Exception as e:
            self.log.log_music("Error", 'retrieve_audio_data', str(e))
        return self.play_url
