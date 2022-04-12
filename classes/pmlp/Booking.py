from datetime import datetime
import locale

class Booking:
    def __init__(self, booking_slot):
        self.time = str(booking_slot['time'])
        self.date = str(booking_slot['date'])
        self.slots = booking_slot['available']

    def get_time(self):
        return self.time

    def get_data(self):
        return self.date

    def get_slots(self):
        return self.slots

    def is_open(self):
        return self.slots > 0

    def get_info(self):
        date = datetime.fromisoformat(self.date)
        locale.setlocale(locale.LC_ALL, 'lv-LV')
        return self.date + " (" + date.strftime('%A').capitalize() + ") **" + self.time + "**"

    def get_booking(self):
        return self.date + " (" + self.time + ") " + str(self.slots)