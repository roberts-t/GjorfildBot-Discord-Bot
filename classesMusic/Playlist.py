import itertools
import random
from collections import deque
from classesMusic.Audio import Audio


class Playlist:
    def __init__(self, voice_id: int):
        self.voice_id = voice_id
        self.queue = deque()
        self.previous_audio = None
        self.is_looping = False
        self.is_paused = True
        self.tracks_played = 0

    def __getitem__(self, item):
        return self.queue[item]

    def add(self, audio: Audio):
        self.queue.append(audio)

    def add_next(self, audio: Audio):
        self.queue.insert(1, audio)

    def insert_after(self, audio_num: int, audio: Audio):
        insert_index = audio_num - self.tracks_played
        if 0 <= insert_index < len(self.queue):
            self.queue.insert(insert_index, audio)

    def remove(self, audio_num: int):
        remove_index = audio_num - self.tracks_played - 1
        del self.queue[remove_index]

    def next(self, skip: bool):
        try:
            if self.tracks_played < 1:
                self.tracks_played += 1
                return self.queue[0].play()

            if not self.is_looping or skip:
                self.previous_audio = self.queue.popleft()
                self.tracks_played += 1

            if len(self.queue) > 0:
                return self.queue[0].play()
            return None
        except Exception as e:
            return None

    def shuffle(self):
        random.shuffle(self.queue)

    def clear(self):
        self.queue.clear()

    def current_audio(self):
        return self.queue[0]
