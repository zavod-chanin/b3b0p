import json
import time
from typing import Union
from tokens.erc20token import Erc20Token
from web3_basis import Web3Client


class WMATIC(Erc20Token):
    def __init__(self, client: Web3Client) -> None:
        self.client = client
        self.token_name = "WMATIC"
        with open(f"abi/wmatic.json", "r") as abi_json:
            abi = json.load(abi_json)
        self.contract = self.client.w3.eth.contract(
            self.client.w3.to_checksum_address(
                "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
            ),
            abi=abi,
        )
        self.decimals = self.contract.functions.decimals().call()

    def wrap(self, value: int):
        try:
            self.client.logger.info("Начал врап MATIC")
            contract_function = self.contract.functions.deposit()
            is_sended = self.client.send_tx(contract_function, value)
            if is_sended:
                self.client.logger.info("Успешно сделал врап MATIC")
        except Exception as e:
            self.client.logger.error(
                f"Произошла ошибка во время врапа {self.token_name}: {e}"
            )
            time.sleep(5)
            return self.wrap(value)
