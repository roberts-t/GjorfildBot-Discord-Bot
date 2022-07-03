# Discord imports
from discord.ext import commands
import discord
import asyncio
from discord import FFmpegPCMAudio
from discord.utils import get

# Custom classes imports
from classesMusic.Playlist import Playlist
from classesMusic.Audio import Audio
from classesMusic.SpotifyAPI import SpotifyAPI
from classesMusic.TrackCollector import TrackCollector
from classesMusic.AudioType import AudioType

# Additional imports
import traceback
import datetime


class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.playlists = dict()
        self.activity_task = None
        self.logger = client.logger
        self.spotify = SpotifyAPI(logger=self.logger)
        self.track_collector = TrackCollector(client.logger)
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
                        if not voice.is_playing() and len(playlist.queue) < 1:
                            to_del.append(channel_id)
                            await voice.disconnect()
                self.logger.log_music(self.logger.LOG_TYPE_INFO, 'check_activity', 'Inactivity result: ' + str(to_del))
                for channel_id in to_del:
                    del self.playlists[channel_id]
                if len(self.playlists) == 0:
                    self.activity_task.cancel()
                    self.activity_task = None
            elif len(self.playlists) == 0:
                self.activity_task.cancel()
                self.activity_task = None
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

    async def get_audio_type_icon(self, audio_type: AudioType):
        audio_type_guild = 926270803182514248
        if audio_type == AudioType.Spotify_Playlist or audio_type == AudioType.Spotify_Track:
            return str(discord.utils.get(self.client.get_guild(audio_type_guild).emojis, name="spotify")) + " "
        elif audio_type == AudioType.Youtube_Playlist or audio_type == AudioType.Youtube_Track:
            return str(discord.utils.get(self.client.get_guild(audio_type_guild).emojis, name="youtube")) + " "
        elif audio_type == AudioType.Search:
            return ":mag: "
        return ""

    async def get_audio_type_short(self, audio_type: AudioType):
        if audio_type == AudioType.Spotify_Playlist or audio_type == AudioType.Spotify_Track:
            return "SP"
        return "YT"

    async def get_queue_track_string(self, audio_num: int, audio: Audio):
        return "\n" + str(audio_num) + ") " + await self.get_audio_type_icon(
            audio.audio_type) + "[" + await self.get_audio_type_short(
            audio.audio_type) + "](" + audio.source_url + ") | " + audio.title + " | [_" + audio.duration + "_]"

    async def insert_track_in_queue(self, ctx, add_next: bool, pos: str, source):
        if await self.is_user_in_voice(ctx):
            try:
                channel = ctx.author.voice.channel
                if channel is not None and channel.id in self.playlists and len(self.playlists[channel.id].queue) > 0:
                    if len(source) < 1:
                        embed_msg = discord.Embed(title="", description=":x: Please provide content to add to queue",
                                                  color=self.client.embed_error)
                        await ctx.send(embed=embed_msg)
                        return
                    playlist = self.playlists[channel.id]
                    source = ' '.join(map(str, source))
                    tracks = self.track_collector.get_audio_data(source)
                    tracks.reverse()
                    for track in tracks:
                        if add_next:
                            playlist.add_next(track)
                        else:
                            playlist.insert_after(int(pos), track)
                    await ctx.message.add_reaction('✅')
                else:
                    embed_msg = discord.Embed(title="", description=":x: Queue is empty, use !play instead",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
            except Exception as e:
                self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'insert_track_in_queue',
                                      str(e) + ' Traceback: ' + str(traceback.format_exc()))
                embed_msg = discord.Embed(title="",
                                          description=":x: Unable to add \"" + source + "\" to the queue :pensive:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['p'])
    async def play(self, ctx, *source):
        if await self.is_user_in_voice(ctx):
            try:
                if len(source) > 0:
                    source = ' '.join(map(str, source))
                    channel = ctx.author.voice.channel
                    if channel is not None:
                        tracks = self.track_collector.get_audio_data(source)

                        # Get playlist
                        if channel.id not in self.playlists:
                            self.playlists[channel.id] = Playlist(channel.id)
                        playlist = self.playlists[channel.id]

                        total_duration = 0.0
                        for track in tracks:
                            playlist.add(track)
                            duration_dt = datetime.datetime.strptime(track.duration, "%M:%S")
                            total_duration += (duration_dt - datetime.datetime(1900, 1, 1)).total_seconds()

                        if playlist.is_paused:
                            playlist.is_paused = False

                        # Get voice client
                        if ctx.guild.voice_client is None:
                            self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play', 'Connecting to voice!')
                            voice = await channel.connect()
                        else:
                            voice = ctx.voice_client

                        def play_next(error=None):
                            track = playlist.next(False)
                            if track is not None and not playlist.is_paused and ctx.guild.voice_client is not None:
                                voice.play(FFmpegPCMAudio(track, **self.FFMPEG_OPTIONS), after=play_next)

                        # Show added message
                        if len(tracks) > 0:
                            audio_type = tracks[0].audio_type
                            embed_msg = discord.Embed(title="Added to the queue")
                            embed_msg.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
                            if audio_type == AudioType.Spotify_Playlist or audio_type == AudioType.Youtube_Playlist:
                                embed_msg.description = ":notes: **" + str(len(tracks)) + "** tracks :notes:"
                                embed_msg.add_field(name=":hourglass: Total duration",
                                                    value=str(datetime.timedelta(seconds=int(total_duration))))
                            elif audio_type == AudioType.Youtube_Track or audio_type == AudioType.Spotify_Track:
                                embed_msg.description = "[" + tracks[0].title + "](" + tracks[0].source_url + ")"
                                embed_msg.add_field(name=":hourglass: Duration", value=tracks[0].duration)
                            elif audio_type == AudioType.Search:
                                embed_msg.description = "[" + tracks[0].title + "](" + tracks[0].source_url + ")"
                                embed_msg.add_field(name=":hourglass: Duration", value=tracks[0].duration)
                                embed_msg.add_field(name=":mag: Search", value=source)
                            await ctx.send(embed=embed_msg)

                        # Start playing if there is not anything playing
                        if not voice.is_playing():
                            if self.activity_task is None:
                                self.logger.log_music(self.logger.LOG_TYPE_INFO, 'play', 'Starting activity checking!')
                                self.activity_task = asyncio.create_task(self.schedule_activity_check())
                            play_next()

            except Exception as e:
                self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'play',
                                      str(e) + ' Traceback: ' + str(traceback.format_exc()))
                embed_msg = discord.Embed(title="", description=":x: Unable to play \"" + source + "\" :pensive:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None:
                    if channel.id in self.playlists:
                        playlist = self.playlists[channel.id]
                        queue = playlist.queue
                        if len(queue) > 0:
                            queue_string = "Currently playing: [" + playlist.current_audio().title + "](" + playlist.current_audio().source_url + ") :musical_note:"
                            queue_string += "\n\n**Tracks in Queue** :arrow_forward:\n"

                            # Display previous track in queue
                            if playlist.previous_audio is not None:
                                queue_string += await self.get_queue_track_string(playlist.tracks_played - 1,
                                                                                  playlist.previous_audio)

                            # Show current track in queue
                            queue_string += "\n**-----------------:arrow_down:CURRENT:arrow_down:-----------------**"
                            queue_string += await self.get_queue_track_string(playlist.tracks_played, queue[0])
                            queue_string += "\n**------------------------------------------------------**"

                            # Show next tracks in queue
                            for i in range(1, len(queue)):
                                if i > 10:
                                    queue_string += "\n\n **" + str(len(queue) - 10) + "** more track/s :headphones:"
                                    break

                                queue_string += await self.get_queue_track_string(playlist.tracks_played + i, queue[i])
                        else:
                            embed_msg = discord.Embed(title="", description=":x: Queue is empty!",
                                                      color=self.client.embed_error)
                            await ctx.send(embed=embed_msg)
                            return
                        embed_msg = discord.Embed(title="Queue", description=queue_string,
                                                  color=self.client.embed_default)
                        await ctx.send(embed=embed_msg)
                else:
                    embed_msg = discord.Embed(title="", description=":x: Queue is empty!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'queue',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command(aliases=['s'])
    async def shazam(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None and voice.is_playing() and channel.id in self.playlists and len(
                        self.playlists[channel.id].queue) > 0:
                    playlist = self.playlists[channel.id]
                    current = playlist.current_audio()
                    embed_msg = discord.Embed(title="Currently playing",
                                              description="[" + current.title + "](" + current.source_url + ")",
                                              color=self.client.embed_default)

                    # Set thumbnail
                    thumbnail = current.thumbnail
                    if thumbnail is not None:
                        embed_msg.set_thumbnail(url=thumbnail)

                    embed_msg.add_field(name="Duration", value=current.duration)
                    embed_msg.add_field(name="Type", value=await self.get_audio_type_icon(current.audio_type))

                    await ctx.send(embed=embed_msg)
                else:
                    embed_msg = discord.Embed(title="", description=":x: Nothing is playing!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'shazam',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command(aliases=['playn'])
    async def play_next(self, ctx, *source):
        await self.insert_track_in_queue(ctx, True, "1", source)

    @commands.command(aliases=['playi'])
    async def play_insert(self, ctx, audio_num, *source):
        await self.insert_track_in_queue(ctx, False, audio_num, source)

    @commands.command()
    async def stop(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None and voice.is_playing():
                    playlist = self.playlists[channel.id]
                    playlist.is_paused = True
                    playlist.clear()
                    voice.stop()
                    await ctx.message.add_reaction('🛑')
                else:
                    embed_msg = discord.Embed(title="", description=":x: Nothing to stop!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'stop',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command(aliases=['next'])
    async def skip(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None and voice.is_playing():
                    voice.stop()
                    await ctx.message.add_reaction('⏭️')
                else:
                    embed_msg = discord.Embed(title="", description=":x: Nothing to skip!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'skip',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command()
    async def pause(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)

                if voice is not None and voice.is_playing():
                    playlist = self.playlists[channel.id]
                    voice.pause()
                    playlist.is_paused = True
                    await ctx.message.add_reaction('⏸️')
                else:
                    embed_msg = discord.Embed(title="", description=":x: Nothing to pause!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'pause',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command(aliases=['start'])
    async def resume(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)

                if voice is not None and not voice.is_playing():
                    playlist = self.playlists[channel.id]
                    voice.resume()
                    playlist.is_paused = False
                    await ctx.message.add_reaction('▶️')
                else:
                    embed_msg = discord.Embed(title="", description=":x: Nothing to resume!",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'resume',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command()
    async def shuffle(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None and voice.is_playing():
                    playlist = self.playlists[channel.id]
                    if len(playlist.queue) > 1:
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
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'shuffle',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command()
    async def clear(self, ctx):
        try:
            self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                      str(ctx.message.created_at))
            if await self.is_user_in_voice(ctx):
                channel = ctx.author.voice.channel
                voice = get(self.client.voice_clients, guild=ctx.guild)
                if voice is not None and voice.is_playing():
                    playlist = self.playlists[channel.id]
                    if len(playlist.queue) > 1:
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
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'clear',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command()
    async def loop(self, ctx):
        try:
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
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'loop',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)

    @commands.command(aliases=['leave', 'dc'])
    async def disconnect(self, ctx):
        try:
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
        except Exception as e:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'disconnect',
                                  str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="", description=":x: Something went wrong :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)


def setup(client):
    client.add_cog(Music(client))
