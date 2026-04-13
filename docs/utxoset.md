# easycoin.UTXOSet

## Classes

### `UTXOSet`

UTXOSet(add_outputs: 'set' = <factory>, sub_outputs: 'set' = <factory>,
add_inputs: 'set' = <factory>, sub_inputs: 'set' = <factory>)

#### Annotations

- add_outputs: set
- sub_outputs: set
- add_inputs: set
- sub_inputs: set

#### Methods

##### `__init__(add_outputs: set = <factory>, sub_outputs: set = <factory>, add_inputs: set = <factory>, sub_inputs: set = <factory>):`

##### `copy() -> UTXOSet:`

Build a copy of the current UTXOSet with no changes.

##### `before(txn: Txn) -> UTXOSet:`

Build a copy of the current UTXOSet that has ephemerally reversed the given
transaction.

##### `after(txn: Txn) -> UTXOSet:`

Build a copy of the current UTXOSet that has ephemerally applied the given
transaction.

##### `can_apply(txn: Txn, debug: bool = False) -> bool:`

Determine if a txn can be applied to the current UTXOSet. This returns False if
a `txn.input_ids[i]` is not an unspent output or if a `txn.output_ids[i]` is
already an input (spent); otherwise returns True. This means that any number of
valid inputs can be burned to fund an already-funded output -- if one of the
`txn.output_ids` has already been added to the UTXOSet and a new transaction
attempts to spend another UTXO to fund it, those EC⁻¹ in the input will be
burned. First checks ephemeral UTXOSet changes, then queries the database.

##### `can_reverse(txn: Txn, debug: bool = False) -> bool:`

Determine if a txn can be reversed in the current UTXOSet. This returns False if
a `txn.output_ids[i]` is not an unspent output or if a `txn.input_ids[i]` is not
an input (spent); otherwise returns True. First checks ephemeral UTXOSet
changes, then queries the database.

##### `apply(txn: Txn, coins: dict[str, Coin] = None):`

Attempt to apply the transaction, persisting the changes to the database. Raises
`ValueError` if it cannot be applied or if there is ephemeral data in the
`UTXOSet` instance. The `coins` dict should map the `Coin` IDs in the `Txn` to
actual `Coin` instances; it is used to create `Input`s and `Output`s with better
detail than just the IDs, which is important for tracking `Wallet` association
in a node.

##### `reverse(txn: Txn, coins: dict[str, Coin] = None):`

Attempt to reverse (or un-apply) the transaction, persisting the changes to the
database. Raises `ValueError` if it cannot be reversed or if there is ephemeral
data in the `UTXOSet` instance. The `coins` dict should map the `Coin` IDs in
the `Txn` to actual `Coin` instances; it is used to create `Input`s and
`Output`s with better detail than just the IDs, which is important for tracking
`Wallet` association in a node.


