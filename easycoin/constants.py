import packify


# coin/stamp constants
_mint_difficulty = 200
_min_coin_mint_size = 100000
_max_stamp_size = 500 * 1024
_max_detail_icon_size = 12 * 1024

# txn constants
_witfee_mult = 1
_witfee_exp = 1
_outcountfee_mult = 32
_outcountfee_exp = 1
_outfee_mult = 1
_outfee_exp = 1
_infee_mult = 1
_infee_exp = 1
_outscriptfee_mult = 1
_outscriptfee_exp = 1
_max_txn_size = _max_stamp_size * 10

# serialization constants
_empty = packify.pack({})

# network
_default_port = 9876
_max_part_size = 62000 # comfortably fits into a single netaio Message
_max_sequence_size = 100
