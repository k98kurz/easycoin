## 0.0.2

- CUI: add nonce field to New Txn -> Edit Output modal
  - Initialized w/ random int for new output
  - Initialized w/ `coin.nonce` for edit output
  - Added button + modal to decompile addresses in coin detail modal
- Added basic network protocol
  - Attempts to connect to bootstrap nodes periodically
  - Uses multi-Part Sequences for synchronizing large data over multiple Messages
  with Merkle Tree inclusion proofs for validation
  - Attempts periodic synchronization with bootstraps and discovered peers
  - Real-time Txn publication
- Added simple headless mode (`easycoin --daemon [--debug]`)
- Under-the-hood improvements:
  - Added `TimeoutCache` class
  - Extended functionality of `LRUCache` class
  - Added 9 new tests

## 0.0.1

- Initial release
  - Core system: Txns, Inputs, Outputs, Coins, Stamps, half-thought-through
  TrustNet+Snapshot+Chunk+Attestation+Confirmation models
  - Full tapescript integration with working cryptographic verification engine
  - CUI made with Textual
  - GameSet system for exporting and importing puzzles in the form of coins with
  hijackable locks (use the "Associate with Wallet" button)
  - Segmented LRU cache system and blob sequencer with Merkle Tree inclusion
  proofs for synchronizing large coins/txns when network protocol is added
  - Test suite with 120 tests

