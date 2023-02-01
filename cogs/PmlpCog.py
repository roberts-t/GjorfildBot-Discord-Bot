from discord.ext import commands
from classes.pmlp.Pmlp import Pmlp
from datetime import datetime, time, timedelta
import asyncio
import config.config as config
import discord


class PmlpCog(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.pmlp_notif_enabled = True
        self.week_count = config.pmlp_default_week_count
        self.check_delay = (30 * 60)
        self.schedule_task = None
        self.location_id = config.pmlp_default_location
        self.service_id = config.pmlp_default_service_id
        self.notification_channel_id = config.pmlp_default_channel_id
        self.dev_channel_id = config.pmlp_dev_channel_id

    @commands.Cog.listener()
    async def on_ready(self):
        if config.production_env and self.pmlp_notif_enabled:
            await self.start_pmlp_check_task()

    async def pmlp_check(self):
        if self.pmlp_notif_enabled:
            pmlp = Pmlp(self.client.logger)
            bookings = pmlp.request(self.week_count, location_id=self.location_id, service_id=self.service_id)
            pmlp.close()
            available_booking = bookings.get_available_booking()

            if available_booking is not None:
                channel = self.client.get_channel(self.notification_channel_id)
                self.client.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_check',
                                       'Sending booking notification, booking:' + available_booking.get_booking())
                try:
                    await channel.send(
                        ':rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/{}/bookings/{} vai https://www.pmlp.gov.lv/lv/pieraksts'.format(
                            self.location_id, self.service_id))
                except Exception as e:
                    self.client.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check', str(e))
                    # Try sending backup message to dev channel
                    try:
                        channel = self.client.get_channel(self.dev_channel_id)
                        await channel.send(
                            ':rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/{}/bookings/{} vai https://www.pmlp.gov.lv/lv/pieraksts'.format(
                                self.location_id, self.service_id))
                    except Exception as e:
                        self.client.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check',
                                               "Backup message failed: " + str(e))

    async def start_pmlp_check_task(self):
        await self.pmlp_check()
        await self.pmlp_check_task()

    async def pmlp_check_task(self):
        try:
            while self.pmlp_notif_enabled:
                daytime_delay = self.check_delay
                # In nighttime check only hourly
                nighttime_delay = 3600
                current_delay = daytime_delay

                # Nighttime is from 1AM to 5AM
                nighttime_start = time(1, 0, 0)
                nighttime_end = time(5, 0, 0)

                current_date = datetime.now()
                current_time = current_date.time()

                # Check if currently it is nighttime
                if nighttime_start <= current_time < nighttime_end:
                    # Combine current date with time to get current date with nighttime end time
                    nighttime_end_date = datetime.combine(current_date, nighttime_end)
                    # Get difference between current time and nighttime end time in full seconds
                    till_nighttime_end = int((nighttime_end_date - current_date).total_seconds())

                    # Check if till nighttime end is less time than nighttime delay and if it is more than 0
                    if nighttime_delay > till_nighttime_end > 0:
                        current_delay = till_nighttime_end + 10
                    elif till_nighttime_end > 0:
                        current_delay = nighttime_delay

                self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_check',
                                "Scheduling PMLP check after {} seconds, current time: {}, next check at: {}"
                                .format(str(current_delay), current_date.strftime("%H:%M:%S"),
                                        (current_date + timedelta(seconds=current_delay)).strftime("%H:%M:%S"))
                                )

                await asyncio.sleep(current_delay)
                await self.pmlp_check()
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check', str(e))


    @commands.command()
    async def pmlp(self, ctx):
        self.pmlp_notif_enabled = not self.pmlp_notif_enabled
        try:
            if self.pmlp_notif_enabled:
                await ctx.send('PMLP notifications enabled! :white_check_mark:')
                self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp', 'PMLP notifications enabled by command!')
                await self.start_pmlp_check_task()
            else:
                self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp', 'PMLP notifications disabled by command!')
                await ctx.send('PMLP notifications disabled! :x:')
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp', str(e))

    @commands.command()
    async def pmlp_delay(self, ctx, minutes: int):
        if minutes is None or not isinstance(minutes, int):
            embed_msg = discord.Embed(title="Please provide delay in minutes! :x:", color=15105570)
            await ctx.send(embed=embed_msg)
            return

        try:
            delay = minutes * 60
            self.check_delay = delay
            self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_delay',
                            'Changed delay between check to {} minutes or {} seconds!'.format(minutes, delay))
            await ctx.message.add_reaction('✅')
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_delay', str(e))

    @commands.command()
    async def pmlp_change(self, ctx, location_id: int, service_id: int):
        if location_id is None or service_id is None or not isinstance(location_id, int) or not isinstance(service_id,
                                                                                                           int):
            embed_msg = discord.Embed(title="Please provide location ID and service ID number! :x:", color=15105570)
            await ctx.send(embed=embed_msg)
            return

        self.service_id = int(service_id)
        self.location_id = int(location_id)
        self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_change',
                        'Changed service id to {} and location id to {}!'.format(self.service_id, self.location_id))
        await ctx.message.add_reaction('✅')

    @commands.command()
    async def pmlp_channel(self, ctx, channel_id):
        if channel_id is None or not isinstance(channel_id, int):
            embed_msg = discord.Embed(title="Please provide channel ID number! :x:", color=15105570)
            await ctx.send(embed=embed_msg)
            return

        self.notification_channel_id = int(channel_id)
        self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_channel',
                        'Changed notification channel id to {}!'.format(self.notification_channel_id))
        await ctx.message.add_reaction('✅')

    @commands.command()
    async def pmlp_weeks(self, ctx, week_count):
        if week_count is None or not isinstance(week_count, int):
            embed_msg = discord.Embed(title="Please provide week count number! :x:", color=15105570)
            self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_weeks',
                            'Changed week count to {}!'.format(self.week_count))
            await ctx.send(embed=embed_msg)
            return

        self.week_count = int(week_count)
        await ctx.message.add_reaction('✅')


def setup(client):
    client.add_cog(PmlpCog(client))
