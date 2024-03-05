import sqlite3
from typing import Union
import pandas
from datetime import datetime
from typing import TYPE_CHECKING


class DataBase:
    def __init__(self, protocol) -> None:
        self.protocol = protocol

    def connect(self) -> None:
        self.conn = sqlite3.connect("../wallets_work_data.db")
        self.cursor = self.conn.cursor()

    def create_table_if_not_exists(self) -> None:
        try:
            self.connect()

            self.cursor.execute(self.protocol.db_create_table_query)

            self.conn.commit()
            self.conn.close()
        except Exception as e:
            print(e)

    def get_stat(self, stat_name: str) -> Union[tuple[None,], str, int, float]:
        try:
            self.connect()

            self.cursor.execute(
                f"SELECT {stat_name} FROM {self.protocol.name} WHERE wallet_address = ?",
                (self.protocol.client.wallet_address,),
            )
            result = self.cursor.fetchone()

            self.conn.commit()
            self.conn.close()

            if result is None:
                return None
            else:
                stat = result[0]

                return stat
        except Exception as e:
            print(e)

    def submit_after_work_data(self) -> None:
        try:
            self.connect()

            quety = f"INSERT OR REPLACE INTO {self.protocol.name} (wallet_address, {', '.join([str(i) for i in self.protocol.db_stats.keys()])}) VALUES (?, {', '.join(['?']*len(self.protocol.db_stats.keys()))})"
            self.cursor.execute(
                quety,
                (self.protocol.client.wallet_address, *self.protocol.db_stats.values()),
            )

            self.conn.commit()
            self.conn.close()
        except Exception as e:
            print(e)

    def import_to_excel(self) -> None:
        try:
            self.connect()

            df = pandas.read_sql_query(f"SELECT * FROM {self.protocol.name}", self.conn)

            current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M")

            df.to_excel(
                (f"results/{current_datetime}.xlsx"), index=False, engine="openpyxl"
            )

            self.conn.commit()
            self.conn.close()
        except Exception as e:
            print(e)
