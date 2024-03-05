# В proxies.txt закинуть прокси в формате USER:PASS@HOST:PORT

# Если в mnemonic.txt фразы, то 1; если приватные ключи, то 0
ACCOUNT_FROM_MNEMONIC = False

USE_PROXY = True

# Задержка между действия (от, до) сек.
DELAY = (30, 90)

# Задержка перед стартом работы кошельков (от, до) сек.
START_DELAY = (1, 1)

# Сколько кошельков запустить одновременно
MAX_THREADS = 1

# Сколько матика использовать для ворка
MATIC_PERC_FOR_USE = (0.97, 0.985)

# 1 круг ворка - 2 мультисвапа и 2 обычных свапа
REPEAT_WORK_COUNT_RANGE = (7, 9)

# Выводить ли баланс на рандомный кошелек, из deposit_wallets.txt.
WITHDRAW_BALANCE = False

# Сколько USDT оставить на балансе после ворка. Поставить False, если не нужно оставлять USDT
KEEP_USDT = (10.1, 14.2)

# Сколько MATIC оставить на балансе после ворка. Поставить False, если не нужно оставлять MATIC
KEEP_MATIC = (0.4, 0.8)

MAX_GAS_PRICE = {"polygon": 100}
