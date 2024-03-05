import json
import time
from typing import Union
from web3_basis import Web3Client
from web3.types import Wei


class Erc20Token:

    tokens = {
        "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619": "WETH",
        "0xD6DF932A45C0f255f85145f286eA0b292B21C90B": "AAVE",
        "0x9a71012B13CA4d3D0Cdc72A177DF3ef03b0E76A3": "BAL",
        "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39": "LINK",
        "0x172370d5Cd63279eFa6d502DAB29171933a610AF": "CRV",
        "0xBbba073C31bF03b8ACf7c28EF0738DeCF3695683": "SAND",
        "0xc2132D05D31c914a87C6611C10748AEb04B58e8F": "USDT",
        "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6": "WBTC",
        "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063": "DAI",
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174": "USDC",
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "MATIC",
        "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270": "WMATIC",
    }

    def __init__(self, client: Web3Client, contract_address: str) -> None:
        self.client = client
        self.token_name = Erc20Token.tokens[contract_address]
        with open(f"abi/Erc20Token.json", "r") as abi_json:
            abi = json.load(abi_json)
        self.contract = self.client.w3.eth.contract(
            self.client.w3.to_checksum_address(contract_address),
            abi=abi,
        )

        self.decimals = self.contract.functions.decimals().call()

    def is_approved_for(self, spender_contract_address: str) -> bool:
        try:
            method_arguments = {
                "owner": self.client.wallet_address,
                "spender": spender_contract_address,
            }

            allowance = self.contract.functions.allowance(
                *tuple(method_arguments.values())
            ).call()

            return bool(allowance)

        except Exception as e:
            self.client.logger.error(
                f"Произошла ошибка во время проверки апрува токена: {e}"
            )

    def approve_for(self, spender_contract_address: str):
        try:
            if (
                not self.is_approved_for(spender_contract_address)
                # or self.contract.address == "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
            ):
                self.client.logger.info(
                    f"Начал апрув {self.token_name} для {spender_contract_address}"
                )
                method_arguments = {
                    "spender": spender_contract_address,
                    "amount": 115792089237316195423570985008687907853269984665640564039457584007913129639935,
                }

                filled_tx = self.contract.functions.approve(
                    *tuple(method_arguments.values())
                )

                is_sended = self.client.send_tx(filled_tx)

                if is_sended:
                    self.client.logger.info(
                        f"Успешно сделал апрув {self.token_name} для {spender_contract_address}"
                    )
                return is_sended
            else:
                return "allready_approved"
        except Exception as e:
            self.client.logger.error(f"Произошла ошибка во время апрува токена: {e}")

    def get_balance(self) -> int:
        try:
            method_arguments = {"account": self.client.wallet_address}

            balance = self.contract.functions.balanceOf(
                *tuple(method_arguments.values())
            ).call()

            return balance

        except Exception as e:
            self.client.logger.error(
                f"Произошла ошибка во время получения баланса токена: {e}"
            )
            time.sleep(5)
            return self.get_balance()

    def is_prepared_to_interact(self, contract_address: str) -> bool:
        try:
            if not self.is_approved_for(contract_address):
                is_sended = self.approve_for(contract_address)
                return is_sended
            else:
                return True
        except Exception as e:
            self.client.logger.error(e)

    def convert_to_wei(self, amount: Union[float, int]) -> int:
        return int(amount * 10**self.decimals)

    def convert_to_ether(self, amount: Union[float, int]) -> Union[float, int]:
        return amount / 10**self.decimals
