import json
from websocket import create_connection
from classes.pmlp.Bookings import Bookings
import ssl
import datetime
import traceback

class Pmlp:

    def __init__(self, logger):
        self.logger = logger
        self.bookings = Bookings()
        self.headers = json.dumps({'Accept-Encoding': 'gzip, deflate, br',
                                   'Accept-Language': 'en-US,en;q=0.9',
                                   'Cache-Control': 'no-cache',
                                   'Connection': 'Upgrade',
                                   'Host': 'bookings.qticketapp.com',
                                   'Origin': 'https://pmlp.qticket.app',
                                   'Pragma': 'no-cache',
                                   'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits',
                                   'Sec-WebSocket-Key': 'pT8MT+X2oBz+EqXi+8M69w==',
                                   'Sec-WebSocket-Version': '13',
                                   'Upgrade': 'websocket',
                                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'
                                   })
        try:
            self.ws = create_connection('wss://bookings.qticketapp.com/socket/bookings/?transport=websocket',
                                        headers=self.headers,
                                        sslopt={"cert_reqs": ssl.CERT_NONE})

            self.logger.log("Info", 'PMLP_init', 'Creating websocket connection...')
            # Read returned socket information
            self.logger.log("Info", 'PMLP_init', str(self.ws.recv()) + " | " + str(self.ws.recv()))
        except Exception as e:
            self.logger.log("Error", 'PMLP_init', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def request(self, week_count: int, service_id: int = 245, location_id: int = 68):
        self.logger.log("Info", 'PMLP_request', 'Requesting bookings for ' + str(week_count) + ' weeks, ' + 'service:' + str(service_id) + ', location:' + str(location_id))
        try:
            # Get monday date
            today = datetime.date.today()
            first_week_day = today - datetime.timedelta(days=today.weekday())

            for i in range(0, week_count):
                date = first_week_day + datetime.timedelta(days=7 * i)
                self.ws.send('42["qticket:bookings:widget",{"type":"get_slots","data":{"locationId":"' + str(location_id) +
                             '","date":"' + str(date) + '","serviceId":"' + str(service_id) + '"}}]')
                response = self.ws.recv()
                self.bookings.add(response)
                if self.bookings.get_available() > 0:
                    self.logger.log("Info", 'PMLP_request',
                                    'Found AVAILABLE bookings: ' + str(self.bookings.get_available()))
                    return self.bookings
        except Exception as e:
            self.logger.log("Error", 'PMLP_request',
                       'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

        self.logger.log("Info", 'PMLP_request', 'Found ' + str(self.bookings.get_all()) + ' bookings, ' + str(self.bookings.get_available()) + ' available')
        return self.bookings

    def close(self):
        try:
            self.ws.close()
            self.logger.log("Info", 'PMLP_close', 'Websocket connection closed!')
        except Exception as e:
            self.logger.log("Error", 'PMLP_close',
                       'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))





