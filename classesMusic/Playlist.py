import itertools
import random
from classesMusic.Audio import Audio


class Playlist:
    def __init__(self, voice_id: int, first_audio: Audio, YDL_OPTIONS: dict):
        self.voice_id = voice_id
        self.queue = [first_audio]
        self.previousAudio = first_audio
        self.currentAudio = first_audio
        self.YDL_OPTIONS = YDL_OPTIONS
        self.is_looping = False
        self.is_playing = False
        self.is_stopped = False

    def __getitem__(self, item):
        return self.queue[item]

    def add(self, audio: Audio):
        # if len(self.queue) < 1:
        #     self.currentAudio = audio
        #     self.previousAudio = audio
        self.queue.append(audio)

    def remove(self, index: int):
        del self.queue[index]

    def next(self, force_next: bool):
        try:
            next_audio = self.currentAudio
            if not self.is_looping or force_next:

                next_audio = self.queue.pop(0)
                self.previousAudio = self.currentAudio
                self.currentAudio = next_audio
            self.is_playing = True
            return next_audio.retrieve_audio_data(self.YDL_OPTIONS)
        except IndexError as e:
            self.is_playing = False
            return None

    def shuffle(self):
        random.shuffle(self.queue)

    def clear(self):
        self.queue.clear()

    def get_queue(self):
        return self.queue
