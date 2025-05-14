from sqloquent import contains, within, belongs_to, has_many
from .Coin import Coin
from .Txn import Txn
from .Wallet import Wallet
from .Input import Input
from .Output import Output

Coin.origins = within(Coin, Txn, 'output_ids')
Coin.spends = within(Coin, Txn, 'input_ids')
Coin.wallet = belongs_to(Coin, Wallet, 'wallet_id')

Txn.inputs = contains(Txn, Coin, 'input_ids')
Txn.outputs = contains(Txn, Coin, 'output_ids')
Txn.wallet = belongs_to(Txn, Wallet, 'wallet_id')

Wallet.txns = has_many(Wallet, Txn, 'wallet_id')
Wallet.coins = has_many(Wallet, Coin, 'wallet_id')
Wallet.inputs = has_many(Wallet, Input, 'wallet_id')
Wallet.outputs = has_many(Wallet, Output, 'wallet_id')

Input.coin = belongs_to(Input, Coin, 'id')
Input.wallet = belongs_to(Input, Wallet, 'wallet_id')
Output.coin = belongs_to(Output, Coin, 'id')
Output.wallet = belongs_to(Output, Wallet, 'wallet_id')

