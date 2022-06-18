from discord.ext import commands
import discord
# Discord imports
import asyncio
from discord import FFmpegPCMAudio
from discord.utils import get

# Custom classes imports
from classesMusic.Playlist import Playlist
from classesMusic.Audio import Audio
from classesMusic.SpotifyAPI import SpotifyAPI

# Additional imports
import re
import yt_dlp
import traceback


class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.url_regex = re.compile(
            r'^(?:http|ftp)s?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        self.playlists = dict()
        self.activity_task = None
        self.currently_playing = None
        self.logger = client.logger
        self.spotify = SpotifyAPI(logger=self.logger)
        self.YDL_OPTIONS = {'format': 'bestaudio/best',
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
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }

    async def schedule_activity_check(self):
        while True:
            # 7 minutes
            await asyncio.sleep(420)
            await self.check_activity()

    async def check_activity(self):
        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'check_activity', 'Performing activity check!')
        try:
            if len(self.playlists) > 0:
                self.logger.log_music(self.logger.LOG_TYPE_INFO, 'check_activity', 'Found active playlists!')
                to_del = []
                for channel_id, playlist in self.playlists.items():
                    channel = self.client.get_channel(int(channel_id))
                    voice = get(self.client.voice_clients, guild=channel.guild)
                    if len(channel.members) < 2:
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'check_activity', 'Channel ' + str(
                            channel_id) + ' has insufficient connected members (' + str(len(channel.members)) + ')')
                        if voice:
                            await voice.disconnect()
                        to_del.append(channel_id)
                    elif voice:
                        if not voice.is_playing() and len(playlist.get_queue()) < 1:
                            to_del.append(channel_id)
                            await voice.disconnect()
                self.logger.log_music(self.logger.LOG_TYPE_INFO, 'check_activity', 'Inactivity result: ' + str(to_del))
                for channel_id in to_del:
                    del self.playlists[channel_id]
                if len(self.playlists) == 0:
                    self.activity_task.cancel()
                    activity_task = None
            elif len(self.playlists) == 0:
                self.activity_task.cancel()
                activity_task = None
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'check_activity',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def is_user_in_voice(self, ctx):
        if ctx.author.voice and ctx.author.voice.channel:
            user = await ctx.guild.fetch_member(ctx.author.id)
            if "DJ" in [role.name for role in user.roles] or user.guild_permissions.administrator:
                return True
            else:
                embed_msg = discord.Embed(title="", description="You do not have permission :pensive:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)
                return False
        else:
            embed_msg = discord.Embed(title="", description=":x: You are not connected to a voice channel",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)
            return False

    async def determine_url_type(self, url):
        if ("youtube" in url or "youtu.be" in url) and ("list" in url or "playlist" in url):
            return "yt-playlist"
        elif "youtube" in url or "youtu.be" in url:
            return "youtube"
        elif "spotify" in url and re.match(self.url_regex, url):
            if "/track/" in url:
                return "sp-track"
            elif "/playlist/" in url:
                return "sp-playlist"
            return "unsupported"
        elif re.match(self.url_regex, url) is None:
            return "search"
        else:
            return "unsupported"

    async def get_playlist_urls(self, playlist_url):
        video_urls = dict()
        try:
            dl_options = dict(self.YDL_OPTIONS)
            dl_options['extract_flat'] = True
            yt_downloader = yt_dlp.YoutubeDL(dl_options)
            yt_info = yt_downloader.extract_info(playlist_url, download=False)

            for info in yt_info['entries']:
                video_urls[info['title']] = info['url']
            self.logger.log_music(self.logger.LOG_TYPE_INFO, 'get_playlist_urls',
                                  'Returning playlist urls: ' + str(video_urls))
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'get_playlist_urls', str(e))
        return video_urls

    @commands.command(aliases=['p'])
    async def play(self, ctx, *url):
        audio = playlist_audios = playlist_titles = None
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            try:
                if len(url) == 0:
                    return
                channel = ctx.author.voice.channel
                url = ' '.join(map(str, url))
                url_type = await self.determine_url_type(url)

                self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play', 'Url type detected: ' + str(url_type))

                youtube_url = url
                if url_type == "youtube" or url_type == "search":
                    if url_type == "youtube":
                        youtube_url = url.split("&list=")[0]

                if url_type == "search":
                    audio = Audio(youtube_url, True, logger=self.logger)
                elif url_type == "youtube":
                    audio = Audio(youtube_url, False, logger=self.logger)
                elif url_type == "sp-track":
                    audio = Audio(self.spotify.get_track_title(url), True, logger=self.logger)
                elif url_type == "yt-playlist":
                    playlist_audios = await self.get_playlist_urls(youtube_url)
                elif url_type == "sp-playlist":
                    playlist_titles = self.spotify.get_playlist_titles(url)
                else:
                    raise Exception("Unsupported url type")

                if channel.id in self.playlists:
                    if url_type != "yt-playlist" and url_type != "sp-playlist":
                        self.playlists[channel.id].add(audio)
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Adding to playlist: ' + str(audio.url))
                    elif url_type == "yt-playlist":
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Adding from playlist: ' + str(playlist_audios.items())[:50])
                        for title, url in playlist_audios.items():
                            audio = Audio(url, False, title, logger=self.logger)
                            self.playlists[channel.id].add(audio)
                    elif url_type == "sp-playlist":
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Adding from playlist: ' + str(playlist_titles)[:50])
                        for title in playlist_titles:
                            audio = Audio(title, True, title, logger=self.logger)
                            self.playlists[channel.id].add(audio)
                else:
                    if url_type != "yt-playlist" and url_type != "sp-playlist":
                        self.playlists[channel.id] = Playlist(channel.id, audio, self.YDL_OPTIONS)
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Creating playlist (' + str(channel.id) + '): ' + str(audio.url))
                    elif url_type == "yt-playlist":
                        cnt = 0
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Creating playlist (' + str(channel.id) + ') from playlist: ' + str(
                                                  playlist_audios.items())[:50])
                        for title, url in playlist_audios.items():
                            audio = Audio(url, False, title, logger=self.logger)
                            if cnt == 0:
                                self.playlists[channel.id] = Playlist(channel.id, audio, self.YDL_OPTIONS)
                            else:
                                self.playlists[channel.id].add(audio)
                            cnt += 1
                    elif url_type == "sp-playlist":
                        cnt = 0
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play',
                                              'Creating playlist (' + str(channel.id) + ') from playlist: ' + str(
                                                  playlist_titles)[:50])
                        for title in playlist_titles:
                            audio = Audio(title, True, title, logger=self.logger)
                            if cnt == 0:
                                self.playlists[channel.id] = Playlist(channel.id, audio, self.YDL_OPTIONS)
                            else:
                                self.playlists[channel.id].add(audio)
                            cnt += 1

                playlist = self.playlists[channel.id]

                if playlist.is_stopped:
                    playlist.is_stopped = False

                def play_next(error=None):
                    source = playlist.next(False)
                    if source is not None and not playlist.is_stopped and ctx.guild.voice_client is not None:
                        voice.play(FFmpegPCMAudio(source, **self.FFMPEG_OPTIONS), after=play_next)

                if ctx.guild.voice_client is None:
                    self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play', 'Connecting to voice!')
                    voice = await channel.connect()
                else:
                    voice = ctx.voice_client

                if not voice.is_playing():
                    if self.activity_task is None:
                        self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play', 'Starting activity checking!')
                        activity_task = asyncio.create_task(self.schedule_activity_check())
                    play_next()
                    if url_type != "yt-playlist" and url_type != "sp-playlist":
                        embed_msg = discord.Embed(title="",
                                                  description="Queued: :musical_note: **" + audio.title + "** :musical_note:",
                                                  color=self.client.embed_default)
                    else:
                        track_count = 0
                        if url_type == "yt-playlist":
                            track_count = str(len(playlist_audios))
                        elif url_type == "sp-playlist":
                            track_count = str(len(playlist_titles))
                        embed_msg = discord.Embed(title="",
                                                  description="Queued: :notes: **" + str(
                                                      track_count) + " tracks** :notes:",
                                                  color=self.client.embed_default)
                    await ctx.send(embed=embed_msg)
                else:
                    if url_type != "yt-playlist" and url_type != "sp-playlist":
                        audio.retrieve_audio_data(self.YDL_OPTIONS)
                        embed_msg = discord.Embed(title="",
                                                  description="Added to the queue: :arrow_right: **" + audio.title + "**",
                                                  color=self.client.embed_default)
                    else:
                        track_count = 0
                        if url_type == "yt-playlist":
                            track_count = str(len(playlist_audios))
                        elif url_type == "sp-playlist":
                            track_count = str(len(playlist_titles))
                        embed_msg = discord.Embed(title="",
                                                  description="**" + str(
                                                      track_count) + " tracks** added to the queue: :arrow_right:",
                                                  color=self.client.embed_default)
                    await ctx.send(embed=embed_msg)
            except Exception as e:
                self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'play', str(e))
                embed_msg = discord.Embed(title="", description=":x: Unable to play \"" + url + "\" :pensive:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                queue = playlist.get_queue()
                queue_string = "Currently playing: [" + playlist.currentAudio.title + "](" + playlist.currentAudio.url + ")"
                if len(queue) > 0:
                    queue_string += "\n\nUp next :arrow_forward:"
                    i = 1
                    for audio in queue:
                        if i > 10:
                            queue_string += "\n\n " + str(len(queue) - 10) + " more track/s"
                            break
                        if audio.is_search:
                            queue_string += "\n♫) " + audio.title
                        else:
                            queue_string += "\n♫) [" + audio.title + "](" + audio.url + ")"
                        i += 1
                embed_msg = discord.Embed(title="Queue:", description=queue_string, color=self.client.embed_default)
                await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title="", description=":x: Queue is empty!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['sm'])
    async def shazam(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                embed_msg = discord.Embed(title="",
                                          description="Currently playing: [" + playlist.currentAudio.title + "](" + playlist.currentAudio.url + ")",
                                          color=self.client.embed_default)
                await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing is playing!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command()
    async def stop(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                playlist.is_stopped = True
                playlist.clear()
                voice.stop()
                await ctx.message.add_reaction('🛑')
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing to stop!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['next'])
    async def skip(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                voice.pause()
                voice.stop()
                await ctx.message.add_reaction('⏭️')
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing to skip!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command()
    async def pause(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            voice = get(self.client.voice_clients, guild=ctx.guild)

            if voice is not None and voice.is_playing():
                voice.pause()
                await ctx.message.add_reaction('⏸️')
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing to pause!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['start'])
    async def resume(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            voice = get(self.client.voice_clients, guild=ctx.guild)

            if voice is not None and not voice.is_playing():
                voice.resume()
                await ctx.message.add_reaction('▶️')
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing to resume!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command()
    async def shuffle(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                if len(playlist.get_queue()) > 1:
                    playlist.shuffle()
                    await ctx.message.add_reaction('🔀')
                else:
                    embed_msg = discord.Embed(title=":x: There is nothing to shuffle :thinking:",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title=":x: There is nothing to shuffle :thinking:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command()
    async def clear(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                if len(playlist.get_queue()) > 1:
                    playlist.clear()
                    await ctx.message.add_reaction('✅')
                else:
                    embed_msg = discord.Embed(title=":x: There is nothing to clear :thinking:",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title=":x: There is nothing to clear :thinking:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command()
    async def loop(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and voice.is_playing():
                playlist = self.playlists[channel.id]
                if playlist.is_looping:
                    playlist.is_looping = False
                    embed_msg = discord.Embed(title="", description="Looping disabled :repeat:",
                                              color=self.client.embed_default)
                else:
                    playlist.is_looping = True
                    embed_msg = discord.Embed(title="", description="Looping enabled :repeat:",
                                              color=self.client.embed_default)
                await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title="", description=":x: Nothing to loop!",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['leave', 'dc'])
    async def disconnect(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if await self.is_user_in_voice(ctx):
            channel = ctx.author.voice.channel
            voice = get(self.client.voice_clients, guild=ctx.guild)
            if voice is not None and ctx.guild.voice_client:
                del self.playlists[channel.id]
                await ctx.message.add_reaction('👋')
                await ctx.guild.voice_client.disconnect()
            else:
                embed_msg = discord.Embed(title="", description=":x: I am not in a voice channel :thinking:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)


def setup(client):
    client.add_cog(Music(client))
