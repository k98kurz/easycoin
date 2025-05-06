# EasyCoin

This project is meant to be a functional demonstration of the UTXO/coin model
of Bitcoin and the earlier "Making a Mint" paper published by the NSA, using the
2010 proposal by Red in a post titled "Not a Suggestion" as inspiration. (Place
the emphasis on the "fun" part of "functional demonstration".)

Bitcoin uses proof-of-work consensus.
Ethereum uses proof-of-stake consensus.
This project uses proof-of-concept consensus: the 1st valid spend seen is the
right one -- no actual consensus, just endless forks. Like I said, it is just
proof-of-concept until I implement something else.

## Conceptual Overview

Coins are conceptually chains of digital signatures, but we will use tapescript
to make it a bit more dynamic (much like how Satoshi wrote a script language in
Bitcoin without mentioning it in the whitepaper). For deterministic
serialization of data, we will use packify.

To generate a fresh coin, the node solves a tapehash PoW challenge specifying a
lock, an amount, a Unix epoch timestamp, and a nonce. The difficulty target will
be the log base 2 of the amount divided by 1000. This fresh coin is then
broadcast to the network; each receiving node validates the PoW; and the hash is
added to the set of UTXOs.

To spend a coin, the owner of the coin creates new coins with the same format:
lock, amount, timestamp, and nonce. However, since the new coins were not made
with PoW, they must be bundled in a transaction with witness data that satisfies
the funding coins' locks and commits to the new output hashes. This transaction
is then broadcast to the network, and the receiving nodes run the following
validation: 1) if the inputs are not members of the UTXO, fail; 2) if the sum of
the output amounts is greater than the sum of the inputs + the transaction fee,
fail; 3) if any of the input locks are not satisfied by the witness data, fail.
Once the transaction is verified, the funding coins are removed from the UTXO
set, and the new coins are added to the UTXO set. (Transaction fees are burned
and will be set at 1 per byte of witness data + 32 per new output.)

The details of a transaction can be discarded after verification by all but the
participants in the transaction.

