import mysql.connector
import traceback
import json
import config.database as config_db


class RiotApiLogger:

    def __init__(self, logger):
        try:
            self.is_enabled = False
            self.logger = logger
            # Connect to database
            self.db = mysql.connector.connect(
                host=config_db.database['host'],
                user=config_db.database['user'],
                password=config_db.database['password'],
                database=config_db.database['database']
            )
            self.db_cursor = self.db.cursor()
        except Exception as e:
            logger.log("Error", 'RiotApiLogger', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def log(self, name, function, json_data):
        if self.is_enabled:
            try:
                json_data = json.dumps(json_data)
                sql = "INSERT INTO `riot_api_logs`(`name`, `function`, `retrieved_json`) VALUES (%s,%s,%s)"

                data_to_insert = (name, function, str(json_data))
                self.db_cursor.execute(sql, data_to_insert)
                self.db.commit()
                # Close connection
                self.db_cursor.close()
                self.db.close()
            except Exception as e:
                self.logger.log("Error", 'RiotApiLogger(log)', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def log_multiple(self, name, function, json_array):
        if self.is_enabled:
            try:
                if isinstance(json_array, list):
                    sql = "INSERT INTO `riot_api_logs`(`name`, `function`, `retrieved_json`) VALUES (%s,%s,%s)"
                    data_to_insert = []
                    for json_data in json_array:
                        json_data = json.dumps(json_data)
                        data_to_insert.append((name, function, str(json_data)))
                    if len(data_to_insert) > 0:
                        self.db_cursor.executemany(sql, data_to_insert)
                        self.db.commit()
                    # Close connection
                    self.db_cursor.close()
                    self.db.close()
                else:
                    self.logger.log("Error", 'RiotApiLogger(log_multiple)','Provided json array not a list ' + str(json_array))
            except Exception as e:
                self.logger.log("Error", 'RiotApiLogger(log_multiple)', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))
