import logging
from threading import RLock
from eth_typing import ChecksumAddress
from datetime import datetime


class LockedLogger:
    def __init__(self, wallet_address: ChecksumAddress, global_lock: RLock) -> None:
        self.wallet_address = wallet_address
        self.logger = logging.getLogger(self.wallet_address)
        self.global_lock = global_lock
        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"log/{self.wallet_address}_{current_datetime}.log"

        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message) -> None:
        with self.global_lock:
            self.logger.info(message)

    def error(self, message) -> None:
        with self.global_lock:
            self.logger.error(message)

    def debug(self, message) -> None:
        with self.global_lock:
            self.logger.debug(message)
