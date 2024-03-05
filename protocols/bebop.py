import random
import time
from typing import Union
from web3 import Web3
import requests
from fake_useragent import UserAgent
from eth_account import Account
from eth_account.messages import encode_typed_data

from database import DataBase
from tokens.erc20token import Erc20Token
from web3_basis import Web3Client, Web3Protocol


class Bebop(Web3Protocol):
    def __init__(self, client: Web3Client) -> None:
        super().__init__(client)
        ua = str(UserAgent.chrome)
        self.name = "bebop"
        self.db_create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self.name} (
            wallet_address TEXT PRIMARY KEY,
            new_single_swap_tx_count INTEGER DEFAULT 0,
            new_multi_swap_tx_count INTEGER DEFAULT 0,
            usdt_balance REAL DEFAULT 0.0,
            matic_balance REAL DEFAULT 0.0,         
            overall_multi_swap_tx_count INTEGER DEFAULT 0,
            overall_single_swap_tx_count INTEGER DEFAULT 0
            
        )
        """
        self.db_stats = {"new_single_swap_tx_count": 0, "new_multi_swap_tx_count": 0}

        self.db = DataBase(self)
        self.main_headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "referrer": "https://bebop.xyz/",
            "referrerPolicy": "strict-origin-when-cross-origin",
            "User-Agent": ua,
        }
        self.swap_available_tokens = {
            "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
            "0xD6DF932A45C0f255f85145f286eA0b292B21C90B",
            "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
            "0xBbba073C31bF03b8ACf7c28EF0738DeCF3695683",
            "0x172370d5Cd63279eFa6d502DAB29171933a610AF",
            "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
            "0x9a71012B13CA4d3D0Cdc72A177DF3ef03b0E76A3",
        }
        self.order_approved_tokens = set()

    def get_approval_signature(self, sell_tokens_list: list[str]):
        try:
            self.client.logger.debug(f"Начал получение сигнатуры для аппрува")
            exp_time = f"{int(time.time()) + 2592000}"
            message = {
                "domain": {
                    "name": "Permit2",
                    "chainId": 137,
                    "verifyingContract": "0x000000000022d473030f116ddee9f6b43ac78ba3",
                },
                "primaryType": "PermitBatch",
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                    "PermitBatch": [
                        {"name": "details", "type": "PermitDetails[]"},
                        {"name": "spender", "type": "address"},
                        {"name": "sigDeadline", "type": "uint256"},
                    ],
                    "PermitDetails": [
                        {"name": "token", "type": "address"},
                        {"name": "amount", "type": "uint160"},
                        {"name": "expiration", "type": "uint48"},
                        {"name": "nonce", "type": "uint48"},
                    ],
                },
                "message": {
                    "details": [],
                    "spender": "0xbeb09000fa59627dc02bb55448ac1893eaa501a5",
                    "sigDeadline": exp_time,
                },
            }
            for i in sell_tokens_list:
                message["message"]["details"].append(
                    {
                        "token": i.lower(),
                        "amount": "1461501637330902918203684832716283019655932542975",
                        "expiration": exp_time,
                        "nonce": 0,
                    },
                )

            self.client.logger.debug(message)

            signable_message = encode_typed_data(full_message=message)
            signature = Account.sign_message(
                signable_message, self.client.private_key
            ).signature.hex()

            self.client.logger.debug(signature)
            self.client.logger.debug("Успешно получил сигнатуру для аппрува")

            return (signature, exp_time)
        except Exception as e:
            self.client.logger.error(
                f"Прозошла ошибка во время получения сигнатуры аппрува для бебопа: {e}"
            )

            self.random_retry_sleep()
            return self.get_approval_signature(sell_tokens_list)

    def approve_tokens(self, sell_tokens_list: list[str], is_retry: bool = False):
        try:
            tokens_for_order_approve = []
            for i in sell_tokens_list:
                if i not in self.order_approved_tokens:
                    token = Erc20Token(self.client, i)

                    is_approved = token.approve_for(
                        "0x000000000022D473030F116dDEE9F6B43aC78BA3"
                    )
                    if is_retry:
                        if (
                            is_approved
                            and is_approved != "allready_approved"
                            or is_approved == "allready_approved"
                            and i not in self.order_approved_tokens
                        ):
                            tokens_for_order_approve.append(i)
                    else:
                        if is_approved and is_approved != "allready_approved":
                            tokens_for_order_approve.append(i)

            if tokens_for_order_approve:

                approval_signature, exp_time = self.get_approval_signature(
                    tokens_for_order_approve
                )

                return tokens_for_order_approve, approval_signature, exp_time

            else:
                return (None, None, None)

        except Exception as e:
            self.client.logger.error(f"Произошла ошибка во время аппрува токенов {e}")
            self.random_retry_sleep()
            return self.approve_tokens(sell_tokens_list, repeat=True)

    def get_quote_for_swap(
        self, amount_list: list[int], sell_tokens: str, buy_tokens: str
    ):

        self.client.logger.debug("Начал получение квоты")

        url = "https://api.bebop.xyz/router/polygon/v1/quote"

        params = {
            "buy_tokens": buy_tokens,
            "sell_tokens": sell_tokens,
            "sell_amounts": ",".join(map(str, amount_list)),
            "taker_address": str(self.client.wallet_address),
            "receiver_address": str(self.client.wallet_address),
            "source": "bebop",
            "include_routes": "PMM",
            "approval_type": "Permit2",
        }

        self.client.logger.debug(params)

        buy_token_ratio = round(random.uniform(0.2, 0.7), 2)

        if len(buy_tokens.split(",")) > 1:
            params["buy_tokens_ratios"] = ",".join(
                map(str, [1 - buy_token_ratio, buy_token_ratio])
            )

        response = requests.get(
            url,
            params=params,
            headers=self.main_headers,
            proxies=self.client.proxies,
        ).json()

        self.client.logger.debug(response)

        quote = response["routes"][0]["quote"]

        return quote

    def get_order_signature(
        self,
        amount_list: list[int],
        sell_tokens_list: list[str],
        buy_tokens_list: list[str],
    ) -> tuple[str, dict]:
        """
        Returns:
           (order_signature, quote)
        """

        self.client.logger.debug("Начал получение сигнатуры для ордера")

        buy_tokens = ",".join(buy_tokens_list)
        sell_tokens = ",".join(sell_tokens_list)

        quote = self.get_quote_for_swap(amount_list, sell_tokens, buy_tokens)
        to_sign_data = quote["toSign"]

        to_sign_data["commands"] = Web3.to_bytes(hexstr=to_sign_data["commands"])
        to_sign_data["taker_amounts"][0][0] = int(to_sign_data["taker_amounts"][0][0])

        to_sign_data["maker_amounts"][0][0] = int(to_sign_data["maker_amounts"][0][0])

        self.client.logger.debug(to_sign_data)

        message = {
            "domain": {
                "name": "BebopSettlement",
                "version": "1",
                "chainId": 137,
                "verifyingContract": "0xbeb09000fa59627dc02bb55448ac1893eaa501a5",
            },
            "primaryType": "Aggregate",
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Aggregate": [
                    {"name": "expiry", "type": "uint256"},
                    {"name": "taker_address", "type": "address"},
                    {"name": "maker_addresses", "type": "address[]"},
                    {"name": "maker_nonces", "type": "uint256[]"},
                    {"name": "taker_tokens", "type": "address[][]"},
                    {"name": "maker_tokens", "type": "address[][]"},
                    {"name": "taker_amounts", "type": "uint256[][]"},
                    {"name": "maker_amounts", "type": "uint256[][]"},
                    {"name": "receiver", "type": "address"},
                    {"name": "commands", "type": "bytes"},
                ],
            },
            "message": to_sign_data,
        }
        signable_message = encode_typed_data(full_message=message)

        order_signature = Account.sign_message(
            signable_message, self.client.private_key
        ).signature.hex()

        self.client.logger.debug(order_signature)
        self.client.logger.debug("Успешно получил сигнатуру для ордера")
        return (order_signature, quote)

    def procces_order(
        self,
        order_signature: str,
        quote,
        approval_signature: Union[str, None],
        exp_time: str,
        tokens_for_order_approve: list[str] = None,
    ) -> bool:
        """
        Returns:
            bool: Order Tx status
        """
        self.client.logger.info("Начал отправку ордера")

        url = "https://api.bebop.xyz/polygon/v2/order"
        quote_id = quote["quoteId"]
        data = {
            "signature": order_signature,
            "quote_id": quote_id,
        }

        if approval_signature:
            data["permit2"] = {
                "signature": approval_signature,
                "approvals_deadline": exp_time,
                "token_addresses": tokens_for_order_approve,
                "token_nonces": [0] * len(tokens_for_order_approve),
            }

        self.client.logger.debug(data)

        response = requests.post(
            url, headers=self.main_headers, json=data, proxies=self.client.proxies
        )

        self.client.logger.debug(response.json())
        if response.json()["status"] == "Success":
            tx_hash = response.json()["txHash"]
            self.client.logger.info(
                f"Успешно отправил ордер. Жду подтверждения транзакции: {tx_hash}"
            )

            tx_status = bool(
                self.client.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)[
                    "status"
                ]
            )

            return tx_status

    @Web3Protocol.retry(max_execution_time=1800, sleep_time=20)
    def swap(
        self,
        sell_tokens_list: list[str],
        buy_tokens_list: list[str] = None,
        amount_list: list[int] = None,
        keep_amount_range: tuple[float, float] = None,
        is_retry: bool = False,
    ) -> list[str]:
        """
        Returns:
            list[str]: Список с купленными токенами, после свапа
        """

        tokens_for_order_approve, approval_signature, exp_time = self.approve_tokens(
            sell_tokens_list, is_retry
        )

        if not amount_list:
            amount_list = []

            for i in sell_tokens_list:
                token = Erc20Token(self.client, i)

                token_balance = token.get_balance()

                while not token_balance:
                    self.client.logger.debug(f"Баланс токена {i} = 0. Пробую еще раз")
                    token = Erc20Token(self.client, i)
                    token_balance = token.get_balance()
                    time.sleep(10)

                if keep_amount_range:
                    keep_amount_wei = token.convert_to_wei(
                        float(round(random.uniform(*keep_amount_range), 4))
                    )

                    sell_amount = token_balance - keep_amount_wei

                else:
                    sell_amount = token_balance

                amount_list.append(sell_amount)

        self.client.logger.info(
            f"Начал свап {sell_tokens_list} : {amount_list} на {buy_tokens_list}"
        )

        if isinstance(buy_tokens_list, int):
            buy_tokens_list = random.sample(
                list(self.swap_available_tokens - set(sell_tokens_list)),
                buy_tokens_list,
            )

        if buy_tokens_list and is_retry:
            buy_tokens_list = random.sample(
                list(
                    self.swap_available_tokens
                    - set(sell_tokens_list)
                    - set(buy_tokens_list)
                ),
                len(buy_tokens_list),
            )

        order_signature, quote = self.get_order_signature(
            amount_list, sell_tokens_list, buy_tokens_list
        )
        is_sended = self.procces_order(
            order_signature,
            quote,
            approval_signature,
            exp_time,
            tokens_for_order_approve,
        )
        if is_sended:
            self.client.logger.info(f"Успешно свапнул. Транзакция подтвердилась")
            self.order_approved_tokens.update(sell_tokens_list)

            return buy_tokens_list

    @Web3Protocol.wait_for_low_gas()
    def run_work(self, start_token: list[str]):

        start_buy_tokens = self.swap(start_token, 2)

        self.db_stats["new_multi_swap_tx_count"] += 1

        self.client.random_delay()

        random.shuffle(start_buy_tokens)

        prev_usd_balance = 0

        for i in start_buy_tokens:
            usd_balance = self.get_token_usd_balance(i)
            if usd_balance > prev_usd_balance:
                single_swap_sell_token = i
                prev_usd_balance = usd_balance

        single_swap_buy_token = self.swap([single_swap_sell_token], 1)

        self.db_stats["new_single_swap_tx_count"] += 1

        start_buy_tokens.remove(single_swap_sell_token)

        self.client.random_delay()

        multi_swap_sell_tokens = single_swap_buy_token + start_buy_tokens

        random.shuffle(multi_swap_sell_tokens)

        multi_swap_buy_token = self.swap(multi_swap_sell_tokens, 1)

        self.db_stats["new_multi_swap_tx_count"] += 1

        self.client.random_delay()

        end_token = self.swap(multi_swap_buy_token, 1)

        self.db_stats["new_single_swap_tx_count"] += 1

        return end_token

    @Web3Protocol.retry(max_retries=10, sleep_time=10)
    def get_usd_prices(self):
        url = "https://api.bebop.xyz/tokens/v1/polygon/prices"

        response = requests.get(
            url=url, headers=self.main_headers, proxies=self.client.proxies
        )

        if response.status_code == 200:

            self.usd_prices = response.json()

    def get_token_usd_balance(self, contract_address: str) -> float:
        usd_price = self.usd_prices[contract_address]

        token = Erc20Token(self.client, contract_address)

        balance = token.convert_to_ether(token.get_balance())

        return usd_price * balance
