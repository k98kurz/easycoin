from sqloquent import contains, within
from .Coin import Coin
from .Txn import Txn
from .Wallet import Wallet

Coin.origins = within(Coin, Txn, 'output_ids')
Coin.spends = within(Coin, Txn, 'input_ids')
Coin.wallet = belongs_to(Coin, Wallet, 'wallet_id')

Txn.inputs = contains(Txn, Coin, 'input_ids')
Txn.outputs = contains(Txn, Coin, 'output_ids')
Txn.wallet = belongs_to(Txn, Wallet, 'wallet_id')

Wallet.txns = has_many(Wallet, Txn, 'wallet_id')
Wallet.coins = has_many(Wallet, Coin, 'wallet_id')

