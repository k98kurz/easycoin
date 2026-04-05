# EasyCoin

This is a toy created for research and experimentation. Maybe it will become
something useful, but until then it will at least be amusing to build.

This project is meant to be a functional demonstration of the UTXO/coin model
of Bitcoin and the earlier "Making a Mint" paper published by the NSA, using the
2010 proposal by Red in a post titled "Not a Suggestion" as inspiration. (Place
the emphasis on the "fun" part of "functional demonstration".)

❌ Bitcoin uses proof-of-work consensus.

❌ Ethereum uses proof-of-stake consensus.

✅ EasyCoin uses proof-of-concept consensus.

## Conceptual Overview

Coins are conceptually chains of digital signatures, but we will use tapescript
to make it a bit more dynamic (much like how Satoshi wrote a script language in
Bitcoin without mentioning it in the whitepaper). For deterministic
serialization of data, we will use packify. Instead of storing the full data for
every transaction and coin forever, we store only the STXO (spend txn outputs
i.e. input hash) and UTXO (unspent txn output hash) sets and the coins held by
our wallet. Since input and output hashes commit to all coin data, we can
validate by requiring the coin data for all inputs and outputs of a transaction,
ensure that the hashes match the provided data, validate that the inputs are
part of the UTXO set (coins were properly created and have not yet been spent),
and that the witness data of the transaction validates against the locks on the
input coins.

#### The native unit of account is the Inverse Energy Credit (EC⁻¹).

The Inverse Energy Credit is a receipt proving that you burned energy doing
cryptographic computations. When you want others to also spend some energy doing
cryptographic computations to verify your transactions, you relinquish an amount
of EC⁻¹ in the transaction. The purpose of this is to prevent someone from
spamming the network and DoSing nodes. In blockchain systems, this is sometimes
referred to as "burning gas fees".

To generate a fresh coin, the node solves a tapehash PoW challenge specifying a
lock, an amount, a Unix epoch timestamp, and a nonce. The difficulty target will
be (coin amount + txn fee overhead) divided by 1000 + a minimum difficulty
parameter (currently 128). This fresh coin is then broadcast to the network;
each receiving node validates 1) that the timestamp is not more than a small
threshold in the past, 2) the PoW meets the threshold, and 3) that the coin has
not already been spent; and the hash of the coin (its ID) is added to the set of
UTXOs. Once the trust net features are added, nodes will create and broadcast an
attestation/countersignature claiming that the txn is valid, and the trust net
will periodically bundle the sets of inputs and outputs into checkpoints.

To spend a coin, the owner of the coin creates new coins with the same format:
lock, amount, timestamp, and nonce. However, since the new coins were not made
with PoW, they must be bundled in a transaction with witness data that satisfies
the funding coins' locks and commits to the new output hashes. This transaction
is then broadcast to the network, and the receiving nodes run the following
validation: 1) if the inputs are not members of the UTXO set, fail; 2) if the
sum of the output amounts is greater than the sum of the inputs + the required
EC⁻¹ burn, fail; 3) if any of the input locks are not satisfied by the witness
data, fail; 4) if any stamp constraints (see below) are not satisified by the
witness data, fail. Once the transaction is verified, the funding coins are
removed from the UTXO set, and the new coins are added to the UTXO set.
(Transaction fees are burned and will be set at 1 per byte of txn data.)

Preventing double spending will be accomplished by maintaining a log of input
hashes (i.e. spent coin IDs) and simply adding an input hash whenever a txn is
received and validated in the absence of a TrustNet configuration. With a TrustNet
configured, that TrustNet's consensus mechanism for validating transactions and
checkpointing the STXO and UTXO sets will be used.

The details of a transaction can be discarded after verification by all but the
participants in the transaction, since the outputs cannot be spent without this data,
but the transaction data itself is of no use to anyone else -- the other participants
of a TrustNet need only track the inputs and outputs to prevent double spending.

#### EasyCoins can have data and code stamped onto them.

After mining a new output, the EC⁻¹ can be spent/burned to create a stamped coin.
Stamps are created by adding the following data to the `Coin.details` dict of the
funded output:

```python
coin.details = {
    'id': b'32 bytes sha256 of all other details except dsh', # equivalent to "so_det" in runtime
    'n': "Stamp note/name/nonce", # str|int|bytes
    'dsh': b'32 bytes sha256 of data and scripts (automatically derived)',
    # all the rest are optional
    'd': {'data': 'dictionary'}, # dict[str, str|int|bool|bytes]
    'L': tapescript.Script.from_src("<tapescript lock for new Stamps">).bytes,
    '_': tapescript.Script.from_src("<tapescript coin lock prefix">).bytes,
    '$': tapescript.Script.from_src("<tapescript coin lock postfix">).bytes,
}
```

This can be done with the `Coin.stamp` method:

```python
details = {
    'd': {'type': 'token', 'name': '$HIT coin'}
}
stamp = Coin.stamp(lock, amount, n, details, net_id, net_state)
```

#### Stamped details carry covenants.

The lock postfix in `coin.details['$']` can be used to enforce a covenant. All
covenants must use `_VERIFY` ops to abort witness validation: since a valid
witness script will cause the lock to evalute to a single `true` value on the
stack, covenants must be constructed such that the result of executing the
witness and lock is not altered if the covenant constraints are followed.

When the stamped coin is sent in a transaction, validation will call
`tapescript.run_auth_scripts([prefix, witness, lock, postfix], ...)`, which will
cause validation to fail if the witness does not satisfy the lock or if the
postfix raises a verification exception (e.g. calling `OP_VERIFY` on anything
but a `True` value).

#### By default, Stamps can only be transferred whole.

In the basic case in which the '$' script is not present, each Stamp can be held
by only one output, and this is done by evaluating a default tapescript lock
postfix during validation with the following form:

```s
get_value s"so_len" push d1 equal_verify
get_value s"so_det" get_value s"ii_det" equal_verify
```

This pulls the `"so_len"` value from the tapescript runtime onto the stack, which
is the integer count of stamped outputs in the transaction. It then pushes the
integer 1 onto the stack and runs `OP_EQUAL_VERIFY`, which fails if the two
values are not equal. This is a covenant that requires that there can be only one
stamped output in the transaction that sends this Stamp.

It then pulls the `"so_det"` value from the tapescript runtime onto the stack,
which is the sha256 hash of the `output_coin.details` (less 'id' and 'dsh')
serialized with `packify.pack`; pushes the sha256 of the `input_coin.details` 
(less 'id' and 'dsh') serialized with `packify.pack` onto the stack; then runs
`OP_EQUAL_VERIFY`. This is a covenant that requires that the Stamp details be
copied without alteration from the input coin to the new output coin.

#### Stamps can be created in a series identified by the data-script-hash.

It is possible to create fungible stamps in a series, which is where the sha256
of the data and embedded scripts is the same for all such stamps. To use these
with an integer amount that must be conserved or burnt in transactions (except
for special stamp issuance transactions that validate against the 'L' script),
the covenant should ensure 1) that all stamped inputs have the same
data-script-hash, and 2) that the sum of the 'n' values of stamped outputs
is less than or equal to the sum of the 'n' values of stamped inputs.

Thus, the '$' script should have the following form:

```s
# set some varibables #
get_value s"si_len" @= il 1
get_value s"ii_dsh" @= s 1
get_value s"so_len" @= ol 1

# ensure all stamped inputs are from the same series #
get_value s"si_dsh"
@il loop {
    push d-1 add_ints d2 @= i
    @s equal_verify
    @i
} pop0

# ensure all stamped outputs are from the same series #
get_value s"so_dsh"
@ol loop {
    push d-1 add_ints d2 @= i
    @s equal_verify
    @i
} pop0

# calculate the sum of stamped inputs #
get_value s"si_n" push d0
@il loop {
    push d-1 add_ints d2 @= i
    add_ints d2
    @i
} pop0

# calculate the sum of stamped outputs #
get_value s"so_n" push d0
@ol loop {
    push d-1 add_ints d2 @= i
    add_ints d2
    @i
} pop0

# ensure stamped output sum <= stamped input sum #
leq verify
```

The CUI interface supports creation of unique stamps and fungible stamp series,
and it allows experimentation with custom covenants, mint locks, and prefix
scripts.

NB: This covenant will become significantly more efficient after the tapescript
0.8.0 update changes how `OP_ADD_INTS` functions (final 2 loops will be replaced
with `@il add_ints` and `@ol add_ints`).

#### Stamp series can also have constraints for initial stamping.

If a stamp's details include 'L', validation of the mint transaction will
execute that tapescript lock. This will occur only when there are no input
stamps with the same dsh.

#### The tapescript runtime cache will have the following serialized values:

- `"i_len"`: int number of inputs
- `"i_a"`: input amounts (in EC⁻¹)
- `"si_len"`: int number of stamped inputs
- `"si_det"`: `sha256(packify.pack(input_coin.details)).digest()` for every stamped `input_coin`
- `"ii_det"`: `sha256(packify.pack(input_coin.details)).digest()` for current `input_coin`
- `"si_dsh"`: sha256 of data and scripts in `input_coin.details` for every `input_coin`
- `"ii_dsh"`: sha256 of data and scripts in `input_coin.details` for current `input_coin`
- `"si_n"`: `input_coin.details['n']` for every stamped `input_coin`
- `"ii_n"`: `input_coin.details['n']` for current `input_coin`
- `"o_len"`: int number of outputs
- `"o_a"`: output amounts (in EC⁻¹)
- `"so_len"`: int number of stamped outputs
- `"so_det"`: `sha256(packify.pack(output_coin.details)).digest()` for every stamped `output_coin`
- `"so_dsh"`: sha256 of data and scripts `output_coin.details` for every stamped `output_coin`
- `"so_n"`: `output_coin.details['n']` for every stamped `output_coin`
- `"sigfield1"`: signature scope (e.g. 'Txn')
- `"sigfield2"`: the current coin hash (input coin or output stamp)
- `"sigfield3"`: sha256 of all input hashes, sorted and concatenated
- `"sigfield4"`: sha256 of all output hashes, sorted and concatenated
- `"timestamp"`: int Unix epoch timestamp (automatically added by tapescript)

The current `input_coin` is the coin whose lock is being evaluated, which may be
a newly stamped output if it has an 'L' script.

#### The wallet implementation is hierarchical, deterministic, and password-protected.

The `Wallet.seed` will be derived from a seed phrase and encrypted before being
saved. Encryption and decryption will be done with a key derived from a password,
and the hash of the decrypted seed will be saved as a checksum to verify during
wallet unlocking.

## Future Development/Experimentation Plans

Future developments/experiments include the following:

1. Explicit trust nets
2. Overlay network with SpeedyMurmurs for routing between overlapping networks
3. Novel consensus mechanisms
4. Attacks against all of the above systems

## Statement Concerning Generative AI Use

Though initially attempted, no vibes were achieved in the creation of this code.
The use of LLMs was limited to primarily commit messages, and secondarily review
and Textual CUI scaffolding. At least 99% of the logic created by AIs was wrong
and had to be replaced; the UI had to be reorganized and pixel-pushed; many
hallucinations had to be excised. The AGENTS.md file in the repo is the scar
that bears witness to the many issues that occurred before I largely gave up on
trying to use coding agents to build out the CUI app.

All core logic is artisanal, free-range, organic, hand-crafted code. Less than
1% of the code in the underlying libraries that I maintain came from AI, and all
of that was rewritten before being published anyway.

## Testing

This project contains 81 tests, most of them unit tests but some integration
tests.

To set up, clone the repository and run the following:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then run the tests with `find tests -name test_*.py -print -exec python {} \;`.

Tests across LANs/the Internet are done manually.

## ISC License

Copyright (c) 2026 Jonathan Voss (k98kurz)

Permission to use, copy, modify, and/or distribute this software
for any purpose with or without fee is hereby granted, provided
that the above copyright notice and this permission notice appear in
all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

