from discord.ext import commands
from classes.pmlp.Pmlp import Pmlp
import datetime
import asyncio
import config.config as config
import discord


class PmlpCog(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.pmlp_notif_enabled = True
        self.week_count = config.pmlp_default_week_count
        self.location_id = config.pmlp_default_location
        self.service_id = config.pmlp_default_service_id
        self.notification_channel_id = config.pmlp_default_channel_id
        self.dev_channel_id = config.pmlp_dev_channel_id

    @commands.Cog.listener()
    async def on_ready(self):
        if config.production_env and self.pmlp_notif_enabled:
            await self.schedule_pmlp_check()

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
                        ':scream_cat: :rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/{}/bookings/{} vai https://www.pmlp.gov.lv/lv/pieraksts'.format(self.location_id, self.service_id))
                except Exception as e:
                    self.client.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check', str(e))
                    # Try sending backup message to dev channel
                    try:
                        channel = self.client.get_channel(self.dev_channel_id)
                        await channel.send(
                            ':scream_cat: :rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/{}/bookings/{} vai https://www.pmlp.gov.lv/lv/pieraksts'.format(self.location_id, self.service_id))
                    except Exception as e:
                        self.client.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check',
                                               "Backup message failed: " + str(e))

    async def schedule_pmlp_check(self):
        # Run first time
        if self.pmlp_notif_enabled:
            await self.pmlp_check()

        # 30 mins before another pmlp check in day time
        day_wait = 1800
        # 3 h before another pmlp check in night time
        night_wait = 10800

        now = datetime.datetime.now().time()
        night_start = datetime.time(1, 0, 0)
        night_end = datetime.time(6, 30, 0)

        if night_start <= now < night_end:
            dt_now = datetime.datetime.combine(datetime.date.today(), now)
            dt_night_end = datetime.datetime.combine(datetime.date.today(), night_end)
            till_night_end = int((dt_night_end - dt_now).total_seconds())
            # Check if till night end is less time than night wait
            if till_night_end < night_wait:
                if till_night_end > 0:
                    wait = till_night_end + 30
                else:
                    wait = day_wait
            else:
                wait = night_wait
        else:
            wait = day_wait

        while self.pmlp_notif_enabled:
            self.logger.log(self.logger.LOG_TYPE_INFO, 'schedule_pmlp_check', 'Scheduled PMLP check after ' + str(
                wait) + ' second sleep, current time: ' + datetime.datetime.now().strftime("%H:%M:%S"))
            await asyncio.sleep(wait)
            await self.pmlp_check()

    @commands.command()
    async def pmlp(self, ctx):
        self.pmlp_notif_enabled = not self.pmlp_notif_enabled

        if self.pmlp_notif_enabled:
            await ctx.send('PMLP notifications enabled! :white_check_mark:')
            self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp', 'PMLP notifications enabled by command!')
            await self.schedule_pmlp_check()
        else:
            self.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp', 'PMLP notifications disabled by command!')
            await ctx.send('PMLP notifications disabled! :x:')

    @commands.command()
    async def pmlp_change(self, ctx, location_id: int, service_id: int):
        if location_id is None or service_id is None or not isinstance(location_id, int) or not isinstance(service_id, int):
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
