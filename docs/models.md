# easycoin.models

## Classes

### `Coin(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes | None
- timestamp: int
- lock: bytes
- amount: int
- nonce: int | Default[0]
- net_id: str | None
- net_state: bytes | None
- wallet_id: str | None
- key_index1: int | None
- key_index2: int | None
- spent: bool | Default[False]
- origins: RelatedCollection
- spends: RelatedCollection
- wallet: RelatedModel

#### Properties

- id_bytes
- lock
- details
- stamp_id: Derives the stamp ID from the stamp details.
- dsh: Derives the dsh (data-script-hash) used for comparing Stamps to see if
they are within a series.
- issue: Returns the sha256 of the 'L' mint lock script if one exists.
- net_id_bytes
- origins: The related `Txn`s. Attempting to set to a non-`Txn` raises a
`TypeError`.
- spends: The related `Txn`s. Attempting to set to a non-`Txn` raises a
`TypeError`.
- wallet: The related `Wallet`. Attempting to set to a non-`Wallet` raises a
`TypeError`.
- trustnet: The related `TrustNet`. Attempting to set to a non-`TrustNet` raises
a `TypeError`.

#### Methods

##### `@classmethod commitment(data: dict) -> str:`

##### `@classmethod generate_id(data: dict) -> str:`

##### `check_size() -> bool:`

Returns True if the serialized details are not too large.

##### `pack() -> bytes:`

Serialize to bytes only what must be cryptographically committed, validated, and
thus transmitted via network.

##### `pack_for_gameset() -> bytes:`

Serialize to bytes what is necessary for the Gameset system. This excludes
wallet associations but includes spent status.

##### `pack_full() -> bytes:`

Serialize full coin to bytes.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> 'Coin':`

Deserialize from bytes.

##### `mint_value() -> int:`

Calculates the mint value of the coin (if it has one).

##### `@classmethod create(lock: bytes | Script, amount: int, net_id: str | None = None, net_state: bytes | None = None, nonce_offset: int = 0) -> Coin:`

Creates a new coin that must be funded or mined. Raises `TypeError` or
`ValueError` for invalid parameters.

##### `@classmethod mine(lock: bytes | Script, amount: int = 100000, net_id: str | None = None, net_state: bytes | None = None, nonce_offset: int = 0) -> Coin:`

Mines a coin with the `amount` of value. Raises `TypeError` or `ValueError` for
invalid parameters.

##### `@classmethod stamp(lock: bytes, amount: int, n: str | bytes | int, optional: dict[str, str | int | bool | bytes] = {}, net_id: str | None = None, net_state: bytes | None = None) -> Coin:`

Create a Stamp.

### `Txn(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes | None
- timestamp: int
- input_ids: str
- output_ids: str
- witness: bytes | None
- wallet_id: str | None
- inputs: RelatedCollection
- outputs: RelatedCollection
- wallet: RelatedModel
- attestations: RelatedCollection
- confirmation: RelatedModel

#### Properties

- input_ids: The list of input IDs. Setting to a type other than list[str]
raises TypeError.
- output_ids: The list of output IDs. Setting to a type other than list[str]
raises TypeError. Output IDs will be sorted automatically.
- details: Optional transaction details in dict form. Setting raises `TypeError`
for non-dict values or `packify.UsageError` if a type not serializable via
packify is used in the dict.
- witness: Witness data dict mapping bytes `coin.id` to bytes witness script
(tapescript byte code).
- inputs: The related `Coin`s. Attempting to set to a non-`Coin` raises a
`TypeError`.
- outputs: The related `Coin`s. Attempting to set to a non-`Coin` raises a
`TypeError`.
- wallet: The related `Wallet`. Attempting to set to a non-`Wallet` raises a
`TypeError`.
- attestations: The related `Attestation`s. Attempting to set to a
non-`Attestation` raises a `TypeError`.
- confirmation: The related `Confirmation`. Attempting to set to a
non-`Confirmation` raises a `TypeError`.

#### Methods

##### `set_timestamp():`

##### `save() -> Txn:`

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> Txn:`

##### `@staticmethod minimum_fee(txn: Txn) -> int:`

Calculates the minimum burn required for the transaction.

##### `validate(debug: bool | str = False, reload: bool = True) -> bool:`

Runs the transaction validation logic. Returns False if a mint Txn has a coin
amount that is greater than the mint value; or if the total amount in outputs is
greater than the total amount in inputs; or if the timestamp of an input is
greater than the timestamp of any output; or if an input lock is not fulfilled
by a witness script; or if a new stamp is not authorized by an 'L' script; or if
a transferred stamp does not validate against its covenants; or if the
serialized txn size is greater than 32 KiB. Returns True if all checks pass.

##### `runtime_cache(coin: Coin):`

Construct the tapescript runtime cache for evaluating the lock of a given coin
within the transaction.

##### `@staticmethod std_stamp_covenant() -> Script:`

Returns the standard covenant ('$' script) for unique stamps. This requires that
there is only one stamped output and that it shares the same stamp ID, or that
the stamp is burned.

##### `@staticmethod std_stamp_token_series_prefix(allow_negatives: bool) -> Script:`

Returns the standard prefix ('_' script) for use with token series covenants and
mint locks. Defines two functions: 0 compares values in a loop; 1 sums all
integers in a loop. Takes up 48-53 bytes; saves 14 (16-2) or 15-20 ((17 or
22)-2) bytes with each invocation of function 0 or 1, respectively. In total,
changes the stamp script size from 174 or 184 to 175 or 180 (depending upon
whether or not `allow_negatives` is `False`), including serialization overhead,
but excluding any mint lock.

##### `@staticmethod std_stamp_token_series_covenant() -> Script:`

Returns the standard covenant ('$' script) for fungible stamps in a token
series. This requires that all stamped inputs and outputs share the same
data-script-hash, and that the sum of output 'n' values is less than or equal to
the sum of the input 'n' values. Requires the standard token series prefix
script to function.

##### `@staticmethod std_requires_burn_mint_lock(rate: int) -> Script:`

Returns a standard mint lock 'L' script that requires burning EC⁻¹ at the
specified `rate` to mint the 'n' value. Raises `TypeError` or `ValueError` for
invalid `rate`. Requires the standard token series prefix script.

##### `@staticmethod std_must_balance_mint_lock():`

Returns a standard mint lock 'L' script that requires the sum of all 'n' values
to equal 0.

### `Address(SqlModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- lock: bytes
- committed_script: bytes | None
- secrets: bytes | None
- nonce: int
- child_nonce: int | None
- wallet_id: str
- imported: bool | Default[False]
- wallet: RelatedModel

#### Properties

- hex: Somewhat human-readable address representation of the lock. The result
includes a 4-byte checksum to detect errors.
- wallet: The related `Wallet`. Attempting to set to a non-`Wallet` raises a
`TypeError`.

#### Methods

##### `coins() -> SqlQueryBuilder:`

Returns a query builder for the coins associated with this address.

##### `pack(/, *, include_wallet_info: bool = False) -> bytes:`

##### `@classmethod unpack(data: bytes) -> Address:`

##### `@staticmethod validate(address: str) -> bool:`

Validate a hex representation of an `Address`. Returns `False` if the checksum
check fails or if the script cannot be decompiled. Raises `TypeError` if the
address is not a `str`.

##### `@staticmethod parse(address: str) -> bytes:`

Parses an address into the lock bytes. Raises `TypeError` if address is not a
`str`. Raises `ValueError` if validation fails.

### `Wallet(HashedModel)`

Hierarchical deterministic wallet. Does not even attempt to comply with crypto
industry standards, but the functionality is conceptually identical. After
unlocking the wallet with the correct password, various types of locks and
witnesses can be generated.

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- seed: bytes
- checksum: bytes
- nonce: int | Default[0]
- pubkeys: bytes | None
- tags: str | None
- txns: RelatedCollection
- coins: RelatedCollection
- addresses: RelatedCollection
- inputs: RelatedCollection
- outputs: RelatedCollection

#### Properties

- pubkeys: Dict mapping (nonce, child_nonce) to bytes(VerifyKey). Serialized by
packify for ease of database persistence.
- secrets: Dict mapping locks to secrets necessary for opening them. Intended
for use with adapter signatures and HTLCs.
- is_locked
- seed: The root seed of the wallet. Accessing raises ValueError if the wallet
is locked.
- txns: The related `Txn`s. Attempting to set to a non-`Txn` raises a
`TypeError`.
- coins: The related `Coin`s. Attempting to set to a non-`Coin` raises a
`TypeError`.
- addresses: The related `Address`s. Attempting to set to a non-`Address` raises
a `TypeError`.
- inputs: The related `Input`s. Attempting to set to a non-`Input` raises a
`TypeError`.
- outputs: The related `Output`s. Attempting to set to a non-`Output` raises a
`TypeError`.

#### Methods

##### `unlock(password: str):`

Unlocking a wallet is done by deriving a key from the password via
pbkdf2_hmac(sha256, 10000) and using it to decrypt the wallet seed. If the
salted sha256 hash of the derived key does not match the checksum, ValueError is
raised instead.

##### `lock():`

Locking the wallet involves dropping the decrypted seed from memory.

##### `encrypt(data: bytes) -> bytes:`

Encrypt the data with the unlocked wallet's key and the seal function from
netaio.crypto. Raises `ValueError` if the wallet is locked.

##### `decrypt(data: bytes) -> bytes:`

Decrypt the data with the unlocked wallet's key and the unseal function from
netaio.crypto. Raises `ValueError` if the wallet is locked.

##### `@staticmethod generate_seed_phrase(wordlist: tuple[str]) -> list[str]:`

Generates a seed phrase from the supplied wordlist using `os.urandom` for
randomness. Raises `TypeError` if the wordlist is not `tuple[str]` and
`ValueError` if it is not 2048 long.

##### `@classmethod create(seed_phrase: list[str], password: str, name: str = '') -> Wallet:`

Create a fresh wallet using the seed phrase protected by the given password.
Does not save to the database.

##### `make_address(lock: bytes | Script, nonce: int, /, *, secrets: dict | None = None, committed_script: bytes | Script | None = None) -> Address:`

Creates an `Address` for this wallet, but does not persist to the database.
Raises `TypeError` for invalid parameters.

##### `export_address(address: Address, /, *, password: str = '') -> bytes:`

Exports an address in a way that is portable between wallets. Decrypts secrets
with wallet key and optionally reencrypts with the given password. Raises
`ValueError` if wallet is locked or if the address secrets could not be
decrypted. Raises `TypeError` for invalid parameter types.

##### `import_address(data: bytes, /, *, password: str = '') -> Address:`

Imports an address that had been previously exported. If a password is supplied,
any secrets included in the serialized address will be decrypted first. Raises
`ValueError` or `struct.error` if a password is required and not supplied, or if
the serialized data is corrupted.

##### `@staticmethod get_lock_type(lock: Script | bytes, address_secrets: dict | None) -> str:`

Get lock type string from lock bytes.

##### `get_seed(nonce: int, child_nonce: int | None = None) -> bytes:`

Derives the seed with the given nonce. If child_nonce is supplied, this process
is done a second time (hierarchical).

##### `get_pubkey(nonce: int, child_nonce: int | None = None) -> VerifyKey:`

Retrieve or generate the pubkey for a given nonce and child_nonce. If the
requested key has not been set in the pubkeys property, this will attempt to
generate it, which will raise a ValueError if the wallet is locked; if this is
successful, it will add the generated pubkey to the pubkeys dict.

##### `get_p2pk_lock(nonce: int, child_nonce: int | None = None, sigflags: str = 'f4') -> Script:`

Generate the pay-to-pubkey lock for the given `nonce` and `child_nonce`. Raises
`ValueError` if the wallet is locked and the necessary pubkey has not yet been
generated. Default sigflags require signing sigfield1 (signature scope),
sigfield2 (coin hash), and sigfield4 (all outputs); i.e. sigfield{3,5,6,7,8} can
be left unsigned.

##### `get_p2pk_witness(nonce: int, txn: 'Txn', coin: 'Coin' = None, child_nonce: int | None = '00') -> Script:`

Generates a valid pay-to-pubkey witness for the given `nonce` and `child_nonce`.
Raises `ValueError` if the wallet is locked. Default sigflags sign all
sigfields.

##### `get_p2pkh_lock(nonce: int = None, child_nonce: int | None = 'f4') -> Script:`

Generate the pay-to-pubkey-hash lock for the given `nonce` and `child_nonce`.
Raises `ValueError` if the wallet is locked and the necessary pubkey has not yet
been generated. Default sigflags require signing sigfield1 (signature scope),
sigfield2 (coin hash), and sigfield4 (all outputs); i.e. sigfield{3,5,6,7,8} can
be left unsigned.

##### `get_p2pkh_witness(nonce: int, txn: 'Txn', coin: 'Coin' = None, child_nonce: int | None = '00') -> Script:`

Generates a valid pay-to-pubkey-hash witness for the given `nonce` and
`child_nonce`. Raises `ValueError` if the wallet is locked. Default sigflags
sign all sigfields.

##### `get_p2tr_lock(nonce: int = None, script: Script | None = None, child_nonce: int | None = 'f4') -> Script:`

Generate the pay-to-taproot lock for the given `nonce` and `child_nonce`. If
script is not supplied, an unspendable locking script is generated, which will
allow only the keyspend witness path. Raises `ValueError` if the wallet is
locked and the necessary pubkey has not yet been generated. Default sigflags
require signing sigfield1 (signature scope), sigfield2 (coin hash), and
sigfield4 (hash of all output hashes); i.e. sigfield{3,5,6,7,8} can be left
unsigned.

##### `get_p2tr_witness_keyspend(nonce: int, txn: 'Txn', coin: 'Coin' = None, script: Script | None = None, child_nonce: int | None = '00') -> Script:`

Generate the pay-to-taproot keyspend witness for the given `nonce` and
`child_nonce`. If script is not supplied, an unspendable locking script is
generated and used instead. Raises `ValueError` if the wallet is locked. Default
sigflags sign all sigfields. Default sigflags sign all sigfields.

##### `get_p2tr_witness_scriptspend(nonce: int, script: Script, child_nonce: int | None = None) -> Script:`

Generate the pay-to-taproot keyspend witness for the given `nonce` and
`child_nonce`. Raises `ValueError` if the wallet is locked. Note that any
constraints within the committed script must be satisfied externally to this
method call -- this only unlocks the scriptspend path.

##### `get_p2gr_lock(nonce: int, child_nonce: int | None = None, sigflags: str = 'f4') -> Script:`

Generate the pay-to-graftroot lock for the given `nonce` and `child_nonce`. Can
be unlocked with a keyspend or surrogate script path. Raises `ValueError` if the
wallet is locked and the necessary pubkey has not yet been generated. Default
sigflags require signing sigfield1 (signature scope), sigfield2 (coin hash), and
sigfield4 (all outputs); i.e. sigfield{3,5,6,7,8} can be left unsigned.

##### `get_p2gr_witness_keyspend(nonce: int, txn: 'Txn', coin: 'Coin', child_nonce: int | None = None, sigflags: str = '00') -> Script:`

Generate the pay-to-graftroot keyspend witness for the given `nonce` and
`child_nonce`, which is a signature and a boolean control signal. Raises
`ValueError` if the wallet is locked. Default sigflags sign all sigfields.

##### `get_p2gr_witness_surrogate(nonce: int, surrogate_script: Script | str, child_nonce: int | None = None) -> Script:`

Generate the pay-to-graftroot surrogate script witness for the given `nonce` and
`child_nonce`, which pushes the surrogate script, a signature for the surrogate
script, and a boolean control flag. Raises `ValueError` if the wallet is locked.
Note that any constraints within the surrogate script must be satisfied
externally to this method call -- this only authorizes and prepares the
execution of the surrogate script.

##### `get_p2gt_lock(nonce: int, child_nonce: int | None = None) -> Script:`

Generate the pay-to-graftap (P2GR in P2TR envelope) lock for the given `nonce`
and `child_nonce`. Unlike regular P2GR, the keyspend path is a regular P2TR
keyspend, while the scriptspend path is exclusively for executing surrogate
scripts. Raises `ValueError` if the wallet is locked and the necessary pubkey
has not yet been generated. Note: tapescript v0.7.2 does not allow sigflags
other than '00' for graftap, which means that all sigfields must be signed; this
will be changed when fixed in the next release of tapescript.

##### `get_p2gt_committed_script(nonce: int, child_nonce: int | None = None) -> Script:`

Generate the pay-to-graftap committed script that allows executing a signed
surrogate script via the scripspend path of the P2TR envelope. Raises
`ValueError` if the wallet is locked and the necessary pubkey has not yet been
generated.

##### `get_p2gt_witness_keyspend(nonce: int, txn: 'Txn', coin: 'Coin', child_nonce: int | None = None, sigflags: str = '00') -> Script:`

Generate the pay-to-graftap keyspend witness for the given `nonce` and
`child_nonce`. This is indistinguishable from any other P2TR keyspend witness.
Raises `ValueError` if the wallet is locked. Default sigflags sign all
sigfields.

##### `get_p2gt_witness_scriptspend(nonce: int, surrogate_script: Script, child_nonce: int | None = None) -> Script:`

Generate the pay-to-taproot scriptspend witness for the given `nonce` and
`child_nonce`, which supplies the committed P2GR script and internal pubkey to
unlock the P2TR envelope's scriptspend path, as well as the P2GR surrogate
script and signature. This is slightly different from raw P2GR in that the
control boolean is excluded since keyspend is handled by the P2TR envelope.
Raises `ValueError` if the wallet is locked. Note that any constraints within
the surrogate script must be satisfied externally to this method call -- this
only authorizes and prepares the execution of the surrogate script via the
scriptspend path of the P2TR envelope.

### `Input(SqlModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- net_id: str | None
- net_state: bytes | None
- commitment: str | None
- wallet_id: str | None
- coin: RelatedModel
- trustnet: RelatedModel
- attestations: RelatedCollection
- confirmations: RelatedCollection

#### Properties

- id_bytes: Return the `id` as bytes (converts hexadecimal id).
- net_id_bytes: Return the `net_id` as bytes (converts hexadecimal id).
- coin: The related `Coin`. Attempting to set to a non-`Coin` raises a
`TypeError`.
- wallet: The related `Wallet`. Attempting to set to a non-`Wallet` raises a
`TypeError`.
- trustnet: The related `TrustNet`. Attempting to set to a non-`TrustNet` raises
a `TypeError`.
- attestations: The related `Attestation`s. Attempting to set to a
non-`Attestation` raises a `TypeError`.
- confirmations: The related `Confirmation`s. Attempting to set to a
non-`Confirmation` raises a `TypeError`.

#### Methods

##### `@classmethod from_coin(coin: Coin) -> Input:`

Prepare an Input from a Coin, copying all necessary values.

##### `check() -> bool:`

Check that the Input ID is the sha256 of the `net_id`, `net_state`, and
`commitment`. Intended to be used for verification during pruning.

##### `pack() -> bytes:`

Serialize to bytes. Includes only the cryptographically relevant fields; i.e.
excludes wallet association.

##### `pack_compact() -> bytes:`

Serialize to bytes in compact form (no `net_id`).

##### `@classmethod unpack(data: bytes, net_id: str | None = None, inject: dict = {}) -> Input:`

Deserialize from bytes. Raises ValueError or TypeError for invalid arguments or
unpackable bytes. If the serialization format was compact, the provided `net_id`
(or None) will be used.

### `Output(SqlModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- net_id: str | None
- net_state: bytes | None
- commitment: str | None
- wallet_id: str | None
- coin: RelatedModel
- trustnet: RelatedModel
- attestations: RelatedCollection
- confirmations: RelatedCollection

#### Properties

- id_bytes: Return the `id` as bytes (converts hexadecimal id).
- net_id_bytes: Return the `net_id` as bytes (converts hexadecimal id).
- coin: The related `Coin`. Attempting to set to a non-`Coin` raises a
`TypeError`.
- wallet: The related `Wallet`. Attempting to set to a non-`Wallet` raises a
`TypeError`.
- trustnet: The related `TrustNet`. Attempting to set to a non-`TrustNet` raises
a `TypeError`.
- attestations: The related `Attestation`s. Attempting to set to a
non-`Attestation` raises a `TypeError`.
- confirmations: The related `Confirmation`s. Attempting to set to a
non-`Confirmation` raises a `TypeError`.

#### Methods

##### `@classmethod from_coin(coin: Coin) -> Output:`

Prepare an Output from a Coin, copying all necessary values.

##### `check() -> bool:`

Check that the Output ID is the sha256 of the `net_id`, `net_state`, and
`commitment`. Intended to be used for verification during pruning.

##### `pack() -> bytes:`

Serialize to bytes. Includes only the cryptographically relevant fields; i.e.
excludes wallet association.

##### `pack_compact() -> bytes:`

Serialize to bytes in compact form (no `net_id`).

##### `@classmethod unpack(data: bytes, net_id: str | None = None, inject: dict = {}) -> Output:`

Deserialize from bytes. Raises ValueError or TypeError for invalid arguments or
unpackable bytes. If the serialization format was compact, the provided `net_id`
(or None) will be used.

### `TrustNetFeature(IntEnum)`

Features enabled for a TrustNet. These flags control which chunk types are
included in snapshots and which validation locks are enforced. `SNAPSHOT_*`
refers to the allowable `ChunkKinds` that can be included in Snapshots. `LOCK_*`
refers to where the `TrustNet.lock` is enforced. `RESERVED*` are reserved for
forward-compatibility. `PROOFS` and `MUTATIONS` will be used in future updates.

#### Methods

##### `@classmethod make_flag(features: set[TrustNetFeature]) -> int:`

##### `@classmethod parse_flag(flags: int = 0) -> set[TrustNetFeature]:`

### `TrustNet(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- lock: bytes
- params: bytes
- delegate_scripts: bytes | None
- root: bytes | None
- members: bytes | None
- quorum: int | None
- root_witness: bytes | None
- active: bool
- state: bytes | None
- coins: RelatedCollection
- snapshots: RelatedCollection
- outputs: RelatedCollection
- inputs: RelatedCollection

#### Properties

- id_bytes
- params
- delegate_scripts
- features
- members
- root
- coins: The related `Coin`s. Attempting to set to a non-`Coin` raises a
`TypeError`.
- snapshots: The related `Snapshot`s. Attempting to set to a non-`Snapshot`
raises a `TypeError`.
- outputs: The related `Output`s. Attempting to set to a non-`Output` raises a
`TypeError`.
- inputs: The related `Input`s. Attempting to set to a non-`Input` raises a
`TypeError`.

#### Methods

##### `pack() -> bytes:`

Serialize public info to bytes for transmission across the network.

##### `@classmethod unpack(data: bytes) -> TrustNet:`

Deserialize info from bytes.

### `Attestation(HashedModel)`

#### Annotations

- table: <class 'str'>
- id_column: <class 'str'>
- columns: tuple[str]
- id: <class 'str'>
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: <class 'str'>
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- txn_id: str | None
- input_ids: str | None
- output_ids: str | None
- witness: <class 'bytes'>
- txn: <class 'sqloquent.interfaces.RelatedModel'>
- inputs: <class 'sqloquent.interfaces.RelatedCollection'>
- outputs: <class 'sqloquent.interfaces.RelatedCollection'>

#### Properties

- input_ids
- output_ids
- txn: The related `Txn`. Attempting to set to a non-`Txn` raises a `TypeError`.
- inputs: The related `Input`s. Attempting to set to a non-`Input` raises a
`TypeError`.
- outputs: The related `Output`s. Attempting to set to a non-`Output` raises a
`TypeError`.

#### Methods

##### `runtime_cache() -> dict:`

Return the tapescript runtime cache.

##### `validate(net_id: str | None = None, reload: bool = True) -> bool:`

Runs Attestation validation logic. Returns False if the witness data does not
validate against the/a relevant TrustNet lock. If `net_id` is not specified,
this will return True if the lock of the TrustNet from any input or output is
satisfied by the witness; if it is specified, it will require that specific
TrustNet lock must be satisfied.

### `Confirmation(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- net_id: str
- txn_id: str | None
- input_ids: str | None
- output_ids: str | None
- witness: bytes
- txn: RelatedModel
- inputs: RelatedCollection
- outputs: RelatedCollection

#### Methods

##### `pack() -> bytes:`

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> Confirmation:`

##### `runtime_cache() -> dict:`

Return the tapescript runtime cache.

### `Snapshot(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- net_id: str
- params: bytes
- timestamp: int
- state: bytes
- chunk_ids: str | None
- witness: bytes
- trustnet: RelatedModel
- chunks: RelatedCollection

#### Properties

- chunk_ids_bytes
- trustnet: The related `TrustNet`. Attempting to set to a non-`TrustNet` raises
a `TypeError`.
- chunks: The related `Chunk`s. Attempting to set to a non-`Chunk` raises a
`TypeError`.

#### Methods

##### `@classmethod create(net_id: str, chunks: list[str] = [], params: bytes = b'', timestamp: int = 0) -> Snapshot:`

Creates a new Snapshot. Stores chunk IDs as comma-separated string, uses current
time if timestamp is 0, and calculates state commitment automatically.

##### `calculate_state() -> bytes:`

Calculates the state commitment of the snapshot.

##### `runtime_cache() -> dict:`

Return the tapescript runtime cache.

##### `validate(reload: bool = True, debug: str | bool = False) -> bool:`

Runs Snapshot validation logic. Returns False if the witness data does not
validate against the TrustNet lock.

### `StampTemplate(SqlModel)`

#### Annotations

- table: <class 'str'>
- id_column: <class 'str'>
- columns: tuple[str]
- id: <class 'str'>
- name: <class 'str'>
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: <class 'str'>
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- description: str | None
- type: str | None
- scripts: bytes | None
- details: bytes | None
- version: str | None
- author: str | None
- tags: str | None

#### Properties

- type: Records the `StampType` of the template. Defaults to unknown. Setting
with anything other than a valid `StampType` or equivalent str will result in a
`TypeError` or `ValueError`.
- scripts: A dict of Stamp scripts ('L', '_', and '$'). Setting raises
`TypeError` or `ValueError` for invalid value, and `ValueError` with serialized
`SyntaxError` or `IndexError` message for tapescript compilation errors (bad
source code).
- details: A dict of Stamp details at the 'd' key; i.e. this data will be
pre-filled into that part of the stamped Coin if this StampTemplate is used.
This is important for Stamp Series, e.g. fungible tokens with a human-readable
name.
- dsh: Derives the dsh (data-script-hash) used for comparing Stamps to see if
they are within a series.
- issue: Returns the sha256 of the 'L' mint lock script if one exists.

### `StampType(Enum)`

### `Chunk(HashedModel)`

#### Annotations

- table: str
- id_column: str
- columns: tuple[str]
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- columns_excluded_from_hash: tuple[str]
- details: bytes
- net_id: str | None
- idx: int
- kind: int
- root: bytes
- parent_ids: str | None
- leaves: bytes
- trustnet: RelatedModel
- snapshots: RelatedCollection
- parents: RelatedCollection
- children: RelatedCollection

#### Properties

- kind
- leaves: The leaves of the Merkle tree. Setting this also sets the root to the
new Merkle tree root. Setting raises `TypeError` if setting to something other
than `list[bytes]` or `ValueError` if the number of leaves exceeds the
`MAX_CHUNK_LEAVES` (default 256) or if the serialized bytes size exceeds
`MAX_CHUNK_SIZE` (default 240*256). (These constraints are intended to make sure
an individual chunk can fit within a UDP datagram.
- root: The Merkle root of the data. Cannot be set directly; set the leaves
instead, and the new root will be calculated and set.
- trustnet: The related `TrustNet`. Attempting to set to a non-`TrustNet` raises
a `TypeError`.
- snapshots: The related `Snapshot`s. Attempting to set to a non-`Snapshot`
raises a `TypeError`.
- parents: The related `Chunk`s. Attempting to set to a non-`Chunk` raises a
`TypeError`.
- children: The related `Chunk`s. Attempting to set to a non-`Chunk` raises a
`TypeError`.

#### Methods

##### `@classmethod create(net_id: str | None, idx: int, kind: ChunkKind, leaves: list[bytes], parents: list[str] = []) -> Chunk:`

Create a Chunk from the required columns/fields. Raises `TypeError` for invalid
arguments.

##### `validate(debug: str | bool = False) -> bool:`

Validates a chunk by recalculating the Merkle root and chunk id. If the
`.trustnet` can be loaded from the database, it will also check to ensure the
`chunk.kind` is allowed by the `self.trustnet.features` flags. If `debug` is
set, debug error messages will be printed on validation failure.

##### `apply() -> tuple[int, list[Exception]]:`

Attempt to apply the Chunk to the local database. Returns the number of records
processed successfully and any errors encountered.

### `ChunkKind(IntEnum)`

Types of data chunks for TrustNet snapshots. Chunks store Merkle tree
commitments to data sets that are checkpointed by snapshots. OUTPUTS and INPUTS
are for UTXOSet management; TXNS is obvious; PROOFS and MUTATIONS are for
forward-compatibility with yet unplanned updates; OTHER is for more general,
non-Snapshot/non-TrustNet use.

### `DeletedModel(SqlModel)`

Model for preserving and restoring deleted HashedModel records.

#### Annotations

- table: str
- id_column: str
- columns: tuple
- id: str
- name: str
- query_builder_class: type[QueryBuilderProtocol]
- connection_info: str
- data: dict
- data_original: MappingProxyType
- _event_hooks: dict[str, list[Callable]]
- model_class: str
- record_id: str
- record: bytes
- timestamp: str

#### Methods

##### `__init__(data: dict | None = None) -> None:`

##### `@classmethod insert(data: dict, /, *, suppress_events: bool = False) -> SqlModel | None:`

Insert a new record to the datastore. Return instance. Raises TypeError if data
is not a dict. Automatically sets a timestamp if one is not supplied.

##### `restore(inject: dict | None = None, /, *, suppress_events: bool = False) -> SqlModel:`

Restore a deleted record, remove from `deleted_records`, and return the restored
model. Raises `ValueError` if `model_class` cannot be found. Raises `TypeError`
if `model_class` is not a subclass of `SqlModel`. Uses `packify.unpack` to
unpack the record. Raises `TypeError` if packed record is not a dict.

## Functions

### `set_connection_info(db_file_path: str):`

Set the connection info for all models to use the specified sqlite3 database
file path.

### `get_migrations() -> dict[str, str]:`

Returns a dict mapping model names to migration file content strs.

### `publish_migrations(migration_folder_path: str, migration_callback: Callable = None):`

Writes migration files for the models. If a migration callback is provided, it
will be used to modify the migration file contents. The migration callback will
be called with the model name and the migration file contents, and whatever it
returns will be used as the migration file contents.

### `automigrate(migration_folder_path: str, db_file_path: str):`

Executes the sqloquent automigrate tool.


