#!/usr/bin/python3
from datetime import datetime
import mysql.connector
import config.database as config_db

class Log:

    def __init__(self, db = None):
        self.file = open("logs/log_file.txt", "a")
        self.db = db
        self.db_cursor = db.cursor()

    def check_database_connection(self):
        if not self.db.is_connected():
            self.db = mysql.connector.connect(
                host=config_db.database['host'],
                user=config_db.database['user'],
                password=config_db.database['password'],
                database=config_db.database['database']
            )
            self.db_cursor = self.db.cursor()

    def get_time(self):
        current_time = datetime.now()
        string_time = current_time.strftime("%d/%m/%Y %H:%M:%S")
        return string_time

    def get_time_mysql(self):
        current_time = datetime.now()
        string_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        return string_time

    def log(self, type, function, data, show_time=True):
        log_message = ""
        if show_time:
            log_message += self.get_time() + " | "

        log_message += type.upper() + " "

        log_message += "(" + function + ") "

        log_message += data

        log_message += '\n'
        # print(log_message)
        self.file.write(log_message)
        self.file.flush()
        #print(data)
        self.check_database_connection()
        sql = "INSERT INTO logs (log_time, log_type, log_function, log_data) VALUES (%s, %s, %s, %s)"
        val = (self.get_time_mysql(), type.upper(), function, data)
        self.db_cursor.execute(sql, val)

        self.db.commit()

    def log_music(self, type, function, data):
        sql = "INSERT INTO music_logs (log_time, log_type, log_function, log_data) VALUES (%s, %s, %s, %s)"
        val = (self.get_time_mysql(), type.upper(), function, data)
        # Check for db connection
        self.check_database_connection()

        self.db_cursor.execute(sql, val)

        self.db.commit()

    def log_music_cmd(self, author, command, args, channel, time):
        sql = "INSERT INTO music_commands (command, arguments, author, channel, time_sent) VALUES (%s, %s, %s, %s, %s)"
        val = (str(command), str(args), str(author), str(channel), str(time))
        # Check for db connection
        self.check_database_connection()

        self.db_cursor.execute(sql, val)

        self.db.commit()