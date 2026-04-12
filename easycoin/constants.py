import packify


# coin/stamp constants
MINT_DIFFICULTY = 200
MIN_COIN_MINT_SIZE = 100000
MAX_STAMP_SIZE = 500 * 1024
MAX_DETAIL_ICON_SIZE = 12 * 1024

# txn constants
WITFEE_MULT = 1
WITFEE_EXP = 1
OUTCOUNTFEE_MULT = 32
OUTCOUNTFEE_EXP = 1
OUTFEE_MULT = 1
OUTFEE_EXP = 1
INFEE_MULT = 1
INFEE_EXP = 1
OUTSCRIPTFEE_MULT = 1
OUTSCRIPTFEE_EXP = 1
MAX_TXN_SIZE = MAX_STAMP_SIZE * 10

# serialization constants
EMPTY_DICT = packify.pack({})
EMPTY_TUPLE = packify.pack(tuple())
EMPTY_LIST = packify.pack([])

# chunk constants
MAX_CHUNK_LEAVES = 1024
MAX_CHUNK_SIZE = 60 * MAX_CHUNK_LEAVES

# network
DEFAULT_PORT = 9876
MAX_PART_SIZE = 62000 # comfortably fits into a single netaio Message
MAX_SEQUENCE_SIZE = 100
