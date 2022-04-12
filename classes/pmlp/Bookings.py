import json
import config.database as config_db
import mysql.connector
from classes.pmlp.Booking import Booking
from classes.Database import Database


class Bookings:
    def __init__(self):
        self.available_bookings = []
        self.db = Database(mysql.connector.connect(
            host=config_db.database['host'],
            user=config_db.database['user'],
            password=config_db.database['password'],
            database=config_db.database['database']
        ))
        self.bookings = []

    def add(self, socket_response: str):
        if socket_response.startswith('42'):
            data = socket_response[2:]
        else:
            data = socket_response
        try:
            json_data = json.loads(data)
            slots = json_data[1]['data']
            for slot in slots:
                booking = Booking(slot)
                self.bookings.append(booking)
                if booking.is_open():
                    booking_lookup = self.db.query_select_one("SELECT id FROM `pmlp_checks` WHERE `date` = '" + booking.date + "' AND `time` = '" + booking.time + "'")
                    if booking_lookup is None or len(booking_lookup) < 1:
                        self.available_bookings.append(booking)
                        self.db.query_modify("INSERT INTO `pmlp_checks` (`date`,`time`) VALUES (%s, %s)", [booking.date, booking.time])
        except Exception as e:
            print(e)

    def get_available(self):
        return len(self.available_bookings)

    def get_all(self):
        return len(self.bookings)

    def get_available_booking(self):
        if len(self.available_bookings) > 0:
            return self.available_bookings[0]
        return None

    def show_all(self):
        for booking in self.bookings:
            print(booking.get_booking())

    def show_available(self):
        if len(self.available_bookings) > 0:
            for booking in self.available_bookings:
                print(booking.get_booking())
        else:
            print('No available bookings!')





