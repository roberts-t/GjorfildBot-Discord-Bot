#!/usr/bin/python3
import config.database as config_db
import mysql.connector


class Database:

    def __init__(self, db):
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

    def query_select(self, query: str):
        try:
            self.check_database_connection()
            self.db_cursor.execute(query)
            result = self.db_cursor.fetchall()
            return result
        except Exception as e:
            return []

    def query_select_one(self, query: str):
        try:
            self.check_database_connection()
            self.db_cursor.execute(query)
            result = self.db_cursor.fetchone()
            return result
        except Exception as e:
            return []

    def query_modify(self, query: str, values: list = None):
        if values is None:
            values = []
        try:
            self.check_database_connection()
            if len(values) != 0:
                self.db_cursor.execute(query, values)
            else:
                self.db_cursor.execute(query)
            self.db.commit()
            return self.db_cursor.rowcount
        except Exception as e:
            return 0
