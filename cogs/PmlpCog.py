from discord.ext import commands
from classes.pmlp.Pmlp import Pmlp
import datetime
import asyncio
import config.config as config


class PmlpCog(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.pmlp_notif_enabled = False

    @commands.Cog.listener()
    async def on_ready(self):
        if config.production_env and self.pmlp_notif_enabled:
            await self.schedule_pmlp_check()

    async def pmlp_check(self):
        if self.pmlp_notif_enabled:
            pmlp = Pmlp(self.client.logger)
            bookings = pmlp.request(10)
            pmlp.close()
            available_booking = bookings.get_available_booking()

            if available_booking is not None:
                channel = self.client.get_channel(505410172819079169)
                self.client.logger.log(self.logger.LOG_TYPE_INFO, 'pmlp_check',
                                       'Sending booking notification, booking:' + available_booking.get_booking())
                try:
                    await channel.send(
                        ':scream_cat: :rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP 3. nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/68/bookings/245 vai https://www.pmlp.gov.lv/lv/pieraksts')
                except Exception as e:
                    self.client.logger.log(self.logger.LOG_TYPE_ERROR, 'pmlp_check', str(e))
                    # Try sending backup message to dev channel
                    try:
                        channel = self.client.get_channel(806602174700191757)
                        await channel.send(
                            ':scream_cat: :rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP 3. nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/68/bookings/245 vai https://www.pmlp.gov.lv/lv/pieraksts')
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


def setup(client):
    client.add_cog(PmlpCog(client))
