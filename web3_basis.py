import random
from threading import RLock
import threading
import time
import traceback
from typing import Literal, Union
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.types import TxParams
from web3.contract.contract import ContractFunction
from web3.exceptions import TimeExhausted
from eth_account.messages import encode_defunct
from functools import wraps


from settings import *
from database import DataBase
from logger import LockedLogger


class Web3Client:
    is_chain_use_eip1559 = {
        "polygon": False,
        "eth": True,
        "zksync": True,
    }

    def __init__(self, mnemonic: str, global_lock: RLock, proxies: str = None) -> None:
        self.rpc = "https://polygon.llamarpc.com"
        self.chain_name = "polygon"
        self.is_chain_use_eip1559 = Web3Client.is_chain_use_eip1559[self.chain_name]
        if proxies:
            self.proxies = {
                "https": f"http://{proxies}",
                "http": f"http://{proxies}",
            }
            self.w3 = Web3(
                Web3.HTTPProvider(self.rpc, request_kwargs={"proxies": self.proxies})
            )
        else:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc))

        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if ACCOUNT_FROM_MNEMONIC:
            self.w3.eth.account.enable_unaudited_hdwallet_features()
            self.account = self.w3.eth.account.from_mnemonic(mnemonic)
        else:
            self.account = self.w3.eth.account.from_key(mnemonic)

        self.private_key = self.account._private_key.hex()
        self.wallet_address = self.w3.to_checksum_address(self.account.address)
        self.global_lock = global_lock
        self.logger = LockedLogger(self.wallet_address, self.global_lock)

    def random_delay(self) -> None:
        sec = random.randint(*DELAY)
        self.logger.info(f"Сплю {sec} сек.")
        time.sleep(sec)

    def random_start_delay(self) -> None:
        sec = random.randint(*START_DELAY)
        self.logger.info(f"Жду {sec} сек. перед стартом")
        time.sleep(sec)

    def get_tx_params(
        self, contract_function: Union[ContractFunction, ChecksumAddress]
    ) -> TxParams:
        try:
            if self.is_chain_use_eip1559 and isinstance(
                contract_function, ContractFunction
            ):
                base_fee = int(
                    1.25 * (self.w3.eth.get_block("latest")["baseFeePerGas"])
                )
                max_priority_fee_per_gas = self.w3.eth.max_priority_fee
                max_fee_per_gas = base_fee + max_priority_fee_per_gas

                return {
                    "to": (
                        contract_function.address
                        if isinstance(contract_function, ContractFunction)
                        else contract_function
                    ),
                    "chainId": self.w3.eth.chain_id,
                    "maxFeePerGas": max_fee_per_gas,
                    "maxPriorityFeePerGas": max_priority_fee_per_gas,
                    "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
                }
            else:
                return {
                    "to": (
                        contract_function.address
                        if isinstance(contract_function, ContractFunction)
                        else contract_function
                    ),
                    "chainId": self.w3.eth.chain_id,
                    "gasPrice": int(1.2 * (self.w3.eth.gas_price)),
                    "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
                }
        except Exception as e:
            self.logger.error(f"Не удалось создать словарь для транзакции: {e}")
            traceback.print_exc()

    def send_tx(
        self,
        contract_function: Union[ContractFunction, ChecksumAddress],
        value: Union[int, Literal["full_balance"]] = 0,
    ) -> bool:

        try:
            self.logger.info("Отправляю транзакцию")

            tx_params = self.get_tx_params(contract_function)

            if isinstance(contract_function, ContractFunction):
                tx_data = contract_function._encode_transaction_data()
                tx_params["data"] = tx_data
                tx_estimated_gas = int(
                    1.1
                    * (
                        self.w3.eth.estimate_gas(
                            {
                                "to": contract_function.address,
                                "from": self.wallet_address,
                                "data": tx_data,
                                "value": 1 if isinstance(value, str) else value,
                            }
                        )
                    )
                )

            else:
                tx_estimated_gas = int(
                    1.1
                    * (
                        self.w3.eth.estimate_gas(
                            {
                                "to": contract_function,
                                "from": self.wallet_address,
                                "value": 1 if isinstance(value, str) else value,
                            }
                        )
                    )
                )

            tx_params["gas"] = tx_estimated_gas

            if value == "full_balance":
                tx_params["value"] = (
                    self.w3.eth.get_balance(self.wallet_address)
                    - tx_estimated_gas * tx_params["gasPrice"]
                )

            else:
                tx_params["value"] = value

            signed_tx = self.w3.eth.account.sign_transaction(
                tx_params, self.private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction).hex()

            tx_status = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)[
                "status"
            ]

            return bool(tx_status)

        except Exception as e:
            self.logger.error(f"Не удалось отправить транзакцию: {e}")

    def get_eth_mainnet_gas_price(self) -> float:
        """
        Returns:
            float: Gwei
        """
        try:
            w3 = Web3(Web3.HTTPProvider("https://rpc.ankr.com/eth"))
            gas_price = w3.from_wei(w3.eth.gas_price, "gwei")
            return gas_price
        except Exception as e:
            self.logger.error(f"Произошла ошибка во время проверки газа: {e}")

    def wait_for_low_gas_price(self) -> None:
        with self.global_lock:
            gas_price = self.get_eth_mainnet_gas_price()
            while gas_price > MAX_MAINNET_GAS_PRICE:
                self.logger.debug(
                    f"Цена газа слишком высокая {round(gas_price, 2)} GWei, жду {MAX_MAINNET_GAS_PRICE} GWei"
                )
                event = threading.Event()
                event.wait(timeout=120)
                gas_price = self.get_eth_mainnet_gas_price()

    def sign_signature(self, message: str):
        return self.w3.eth.account.sign_message(
            encode_defunct(text=message), self.private_key
        )


class Web3Protocol:

    class MaxRetriesExceededError(Exception):
        pass

    def __init__(self, client: Web3Client) -> None:
        self.client = client
        self.name = client.chain_name
        self.db = DataBase(self)
        self.db_create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self.name} (
            wallet_address TEXT PRIMARY KEY,
            new_tx_count INTEGER DEFAULT 0,
            overall_tx_count INTEGER DEFAULT 0,
            native_balance REAL DEFAULT 0.0
        )
        """
        self.db_stats = {"new_tx_count": 0}

    def random_repeat_sleep(self, sleep_time: int = 10):
        time.sleep(
            random.randint(
                int(sleep_time - sleep_time / 3), int(sleep_time + sleep_time / 3)
            )
        )


def retry(
    func, max_retries: int = 3, sleep_time: int = 5, max_execution_time: int = None
):
    @wraps(func)
    def wrapper(self: Web3Protocol, *args, **kwargs):
        attempts = 0
        start_time = time.time()

        while attempts < max_retries:
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                self.client.logger.error(
                    f"Произошла ошибка во время выполнения функции {func.__qualname__}: {e.__class__.__name__}: {e}"
                )
                attempts += 1
                self.client.logger.info(f"Пробую еще раз через несколько секунд...")
                self.random_repeat_sleep(sleep_time)

            elapsed_time = time.time() - start_time

            if max_execution_time is not None and elapsed_time >= max_execution_time:
                raise Web3Protocol.MaxRetriesExceededError(
                    f"Превышено максимальное время выполнения ({max_execution_time} секунд). Функцию не удалось выполнить."
                )

        raise Web3Protocol.MaxRetriesExceededError(
            f"Достигнуто максимальное количество повторений ({max_retries}). Функцию не удалось выполнить."
        )

    return wrapper
