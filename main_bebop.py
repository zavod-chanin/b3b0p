from concurrent.futures import ThreadPoolExecutor
import random
import threading
import time
import traceback
from protocols.bebop import Bebop
from tokens.erc20token import Erc20Token
from tokens.wmatic import WMATIC

from web3_basis import Web3Client, Web3Protocol

from settings import *


def worker(mnemonic: str, global_lock: threading.RLock, proxy: str = None):
    try:
        with global_lock:
            if proxy:
                client = Web3Client(mnemonic, global_lock, proxy)
            else:
                client = Web3Client(mnemonic, global_lock)

        client.random_start_delay()

        if client.w3.is_connected():
            client.logger.info("Подключился к кошельку, начинаю работу")

        wmatic = WMATIC(client)
        wmatic.wrap(
            int(
                client.w3.eth.get_balance(client.wallet_address)
                * random.uniform(*MATIC_PERC_FOR_USE)
            )
        )
        client.random_delay()
        bebop = Bebop(client)
        bebop.db.create_table_if_not_exists()
        bebop.get_usd_prices()

        start_sell_token = random.sample(list(bebop.swap_available_tokens), 1)

        client.logger.info("Обмениваю WMATIC на токен")
        bebop.swap(
            [wmatic.contract.address],
            start_sell_token,
        )

        client.random_delay()
        ACTUAL_REPEAT_WORK_COUNT = random.randint(*REPEAT_WORK_COUNT)
        client.logger.info(
            f"Начал круги свапов. Количество: {ACTUAL_REPEAT_WORK_COUNT}"
        )

        for _ in range(ACTUAL_REPEAT_WORK_COUNT):
            start_sell_token = bebop.run_work(start_sell_token)
            client.random_delay()

        client.logger.info("Успешно сделал круги")

        if KEEP_USDT:

            if start_sell_token[0] != "0xc2132D05D31c914a87C6611C10748AEb04B58e8F":

                client.logger.info("Начал обмен последнего токена на USDT")

                bebop.swap(
                    start_sell_token, ["0xc2132D05D31c914a87C6611C10748AEb04B58e8F"]
                )

                bebop.db_stats["new_single_swap_tx_count"] += 1

                client.random_delay()

            usdt = Erc20Token(client, "0xc2132D05D31c914a87C6611C10748AEb04B58e8F")

            bebop.swap(
                ["0xc2132D05D31c914a87C6611C10748AEb04B58e8F"],
                ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"],
                keep_amount_range=KEEP_USDT,
            )

        else:
            bebop.swap(
                [start_sell_token],
                ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"],
            )
        bebop.db_stats["new_single_swap_tx_count"] += 1

        client.random_delay()

        if WITHDRAW_BALANCE:

            client.logger.info("Начал вывод MATIC")
            with global_lock:
                with open("deposit_wallets.txt", "r") as file:
                    deposit_wallets_list = [line.strip() for line in file.readlines()]

            deposit_wallet = deposit_wallets_list.pop()

            with global_lock:
                with open(f"deposit_wallets.txt", "w") as file:
                    for j in deposit_wallets_list:
                        file.write(f"{j}\n")

            client.logger.info(f"Получил кошелек для вывода MATIC: {deposit_wallet}")

            if KEEP_MATIC:
                keep_value = random.uniform(*KEEP_MATIC)

                client.logger.info(f"Оставлю {keep_value} MATIC на балансе")

                withdraw_value = int(
                    client.w3.eth.get_balance(client.wallet_address)
                    - client.w3.to_wei(keep_value, "ether")
                )

                is_sended = client.send_tx(
                    client.w3.to_checksum_address(deposit_wallet), withdraw_value
                )
            else:
                client.logger.info(f"Вывожу весь баланс MATIC")

                is_sended = client.send_tx(
                    client.w3.to_checksum_address(deposit_wallet), "full_balance"
                )

            if is_sended:
                client.logger.info("Успешно вывел MATIC")

        client.logger.info("Успешно закончил работу без ошибок")

        with open("ready_wallets.txt", "a") as file:
            file.write(f"{mnemonic}\n")

    except Exception as e:
        client.logger.error(e)
        traceback.print_exc()

    client.logger.debug("Сохраняю статистику в базу данных")

    usdt = Erc20Token(client, "0xc2132D05D31c914a87C6611C10748AEb04B58e8F")

    bebop.db_stats["usdt_balance"] = float(
        round(usdt.convert_to_ether(usdt.get_balance()), 2)
    )
    client.logger.info(f'Оставшийся баланс USDT: {bebop.db_stats["usdt_balance"]}')

    bebop.db_stats["matic_balance"] = float(
        round(
            client.w3.from_wei(
                client.w3.eth.get_balance(client.wallet_address), "ether"
            ),
            4,
        )
    )

    client.logger.info(f'Оставшийся баланс MATIC: {bebop.db_stats["matic_balance"]}')

    overall_multi_swap_tx_count = bebop.db.get_stat("overall_multi_swap_tx_count")
    overall_single_swap_tx_count = bebop.db.get_stat("overall_single_swap_tx_count")

    client.logger.info(
        f'Сделал мультисвапов : {bebop.db_stats["new_multi_swap_tx_count"]}'
    )
    client.logger.info(
        f'Сделал обычных свапов : {bebop.db_stats["new_single_swap_tx_count"]}'
    )

    if overall_multi_swap_tx_count is None or overall_single_swap_tx_count is None:
        overall_multi_swap_tx_count = 0
        overall_single_swap_tx_count = 0

    bebop.db_stats["overall_multi_swap_tx_count"] = (
        bebop.db_stats["new_multi_swap_tx_count"] + overall_multi_swap_tx_count
    )
    bebop.db_stats["overall_single_swap_tx_count"] = (
        bebop.db_stats["new_single_swap_tx_count"] + overall_single_swap_tx_count
    )

    bebop.db.submit_after_work_data()


def main() -> None:
    with open("mnemonic.txt", "r") as mnemonic_file:
        mnemonic_phrases = [line.strip() for line in mnemonic_file.readlines()]
    random.shuffle(mnemonic_phrases)

    open("ready_wallets.txt", "w").close()

    global_lock = threading.RLock()

    if USE_PROXY:
        with open("proxies.txt", "r") as proxy_file:
            proxies = [line.strip() for line in proxy_file.readlines()]
        random.shuffle(proxies)

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            for i, mnemonic in enumerate(mnemonic_phrases):
                executor.submit(worker, mnemonic, global_lock, proxies[i])
    else:
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            for mnemonic in mnemonic_phrases:
                executor.submit(worker, mnemonic, global_lock)


if __name__ == "__main__":
    main()
