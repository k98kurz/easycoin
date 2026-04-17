from collections import deque
from netaio import (
    UDPNode, Peer, Body, Message, MessageType, DefaultPeerPlugin,
    make_error_msg, make_not_found_msg, make_not_permitted_msg,
    make_ok_msg, make_respond_uri_msg
)
from netaio.asymmetric import X25519CipherPlugin
from netaio.node import get_ip
from easycoin.cache import LRUCache, CacheKind
from easycoin.config import get_config_manager
from easycoin.constants import DEFAULT_PORT
from easycoin.cryptoworker import work, submit_txn_job
from easycoin.errors import type_assert, value_assert
from easycoin.models import Coin, Txn, Input, Output
from easycion.sequence import Part, Sequence, get_sequence, get_part
import os


conf = get_config_manager()
seed = os.urandom(32)
cipher_plugin = X25519CipherPlugin({
    'seed': seed,
})
udpnode = UDPNode(port=DEFAULT_PORT)
udpnode.local_peer = Peer(
    addrs={(get_ip(), DEFAULT_PORT)}, id=bytes(cipher_plugin.vkey),
    data=DefaultPeerPlugin().encode_data({
        "pubkey": bytes(cipher_plugin.pubk),
        "vkey": bytes(cipher_plugin.vkey),
    })
)
sync_cache = LRUCache('sync', CacheKind.RECEIVE, conf.get('sync_cache_size'))
metadata_cache = LRUCache.get_instance('metadata', CacheKind.SEND, 10)
_run_node = True


# main node controls
def stop():
    global _run_node
    _run_node = False

async def run_node():
    await udpnode.start()
    await udpnode.manage_peers_automatically(app_id=b'easycoin')
    while _run_node:
        await asyncio.sleep(0.1)


# metadata helper + handlers
def _get_metadata(model, cols: list[str]):
    meta = metadata_cache.get(model.__name__)
    if meta:
        return meta

    meta = {
        'count': model.query().count(),
    }
    if not meta['count']:
        return packify.pack(meta)
    for c in cols:
        meta['cols'] = {
            'min': model.query().order_by(c, 'asc').first().data.get[c, None],
            'max': model.query().order_by(c, 'desc').first().data.get[c, None],
        }
    meta = packify.pack(meta)
    metadata_cache.put(model.__name__, meta)
    return meta

@udpnode.on((MessageType.REQUEST_URI, b'txns'))
def _respond_with_txns_metadata(msg: Message, addr: tuple[str, int]):
    return make_respond_uri_msg(_get_metadata(Txn, ['timestamp']), msg.body.uri)

@udpnode.on((MessageType.REQUEST_URI, b'coins'))
def _respond_with_coins_metadata(msg: Message, addr: tuple[str, int]):
    return make_respond_uri_msg(_get_metadata(Coin, ['timestamp']), msg.body.uri)

# main request router
@udonode.on((MessageType.REQUEST_URI,))
def route_request(msg: Message, addr: tuple[str, int]):
    if msg.body.uri[:4] == b'txn:':
        return _route_request_txn_scope(msg, addr)
    elif msg.body.uri[:5] == b'coin:'
        return _route_request_coin_scope(msg, addr)
    return make_not_found_msg.body.uri=msg.body.uri)

# main respond router (pull synchronizer)
@udpnode.on((MessageType.RESPOND_URI,)
def route_respond(msg: Message, addr: tuple[str, int]):
    if msg.body.uri[:4] == b'txn:':
        return _route_respond_txn_scope(msg, addr)
    elif msg.body.uri[:5] == b'coin:':
        return _route_respond_coin_scope(msg, addr)
    return make_not_found_msg.body.uri=msg.body.uri)

# txn scope routers + handlers
def _route_request_txn_scope(msg: Message, addr: tuple[str, int]):
    if msg.body.uri == b'txn:list':
        return _get_txn_list(msg, addr)
    elif len(msg.body.uri) == 36: # b'txn:{32-byte id}'
        return _get_txn_seq(msg, addr)
    elif len(msg.body.uri) == 38: # b'txn:{32-byte id}:{part_idx}'
        return _get_txn_part(msg, addr)
    else:
        return make_error_msg(b'malformed URI for the txn scope', uri=msg.body.uri)

def _get_txn_list(msg: Message, addr: tuple[str, int]):
    """Paginated handler for listing available txn ids."""
    total = Txn.query().count()
    offset, limit = 0, MAX_PART_SIZE // 40 # allow for overhead
    if msg.body.content:
        try:
            params = packify.unpack(msg.body.content)
            type_assert(type(params) is dict)
            offset = params.get('offset', 0)
        except:
            return make_error_msg(b'malformed request', uri=msg.body.uri)

    key = f'txn:ids:{offset}'
    txn_ids = metadata_cache.get(key)
    if txn_ids:
        return make_respond_uri_msg(txn_ids, uri=msg.body.uri)

    sqb = Txn.query().order_by('timestamp', 'asc').select(['id'])
    txn_ids = packify.pack([
        bytes.fromhex(t.id) for t in
        sqb.skip(offset).take(limit)
    ])
    metadata_cache.put(key, txn_ids)
    return make_respond_uri_msg(txn_ids, uri=msg.body.uri)

def _get_txn_seq(msg: Message, addr: tuple[str, int]):
    try:
        seq = get_sequence(Txn, msg.body.uri[:-32].hex(), CacheKind.SEND)
        return make_respond_uri_msg(seq.pack(), uri=msg.body.uri)
    except ValueError:
        return make_not_found_msg.body.uri=msg.body.uri)

def _get_txn_part(msg: Message, addr: tuple[str, int]):
    try:
        # b'txn:{id}:{part_idx}'
        txn_id = msg.body.uri[4:36]
        part_idx = int.from_bytes(msg.body.uri[37:], 'big')
        part = get_part(Txn, txn_id, CacheKind.SEND, idx)
        return make_respond_uri_msg(part.pack(), uri=msg.body.uri)
    except ValueError:
        return make_not_found_msg.body.uri=msg.body.uri)

def _route_respond_txn_scope(msg: Message, addr: tuple[str, int]):
    if len(msg.body.uri) == 36: # sequence; b'txn:{id}'
        return _synchronize_txn_seq(msg, addr)
    elif len(msg.body.uri) == 38: # part; b'txn:{id}:{part_idx}'
        return _synchronize_txn_part(msg, addr)

def _synchronize_txn_seq(msg: Message, addr: tuple[str, int]):
    txn_id_bytes = msg.body.uri[:-32]
    txn_id = msg.body.uri[:-32].hex()
    if Txn.find(txn_id):
        return # we already have it, so skip
    try:
        seq = Sequence.unpack(msg.body.content)
    except:
        return make_error_msg(b'malformed Sequence (Txn)', uri=msg.body.uri)
    scz = conf.get('sequence_cache_size', 20)
    cache = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
    key = f'txn:{txn_id}'
    seq2 = cache.get(key)
    if seq2:
        seq = seq2
    else:
        cache.put(key, seq)

    # see if any parts are in the cache and populate to the sequence parts
    pcz = conf.get('parts_cache_size', 1000)
    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
    missing = []
    for i in range(seq.count):
        if seq.has_part(i):
            continue
        key = f'txn:{txn_id}:{i}'
        part = cache.get(key)
        if part:
            try:
                seq.add_part(part)
            except:
                cache.remove(key) # invalid
                missing.append(i)
        else:
            missing.append(i)

    # request up to one missing part and add the rest to synchronization cache
    if missing:
        for m in missing[1:]:
            sync_cache.put(f'txn:{txn_id}:{m}', addr)
        return Message.prepare(
            Body.prepare(
                b'', uri=b'txn:'+txn_id_bytes+':'+missing[0].to_bytes(1, 'big')
            ),
            MessageType.REQUEST_URI
        )

    # otherwise, all parts have been accumulated, so should be able to reconstruct
    try:
        txn = Txn.unpack(seq.reconstruct()
        txn.save()
        publish_txn(txn)
    except:
        ...

def _synchronize_txn_part(msg: Message, addr: tuple[str, int]):
    txn_id = msg.body.uri[4:36]
    if Txn.find(txn_id.hex():
        continue # skip since we already have the record
    part_idx = int.from_bytes(msg.body.uri[37:], 'big')
    try:
        part = Part.unpack(msg.body.content)
        assert part.validate()
        assert part.record_type == 'Txn'
        assert part.record_id == txn_id.hex()
        assert part.idx == part_idx
    except:
        return make_error_msg(b'malformed Part (Txn)', uri=msg.body.uri)
    pcz = conf.get('parts_cache_size', 1000)
    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
    key = f'txn:{txn_id}:{idx}'
    part2 = cache.get(key)
    if not part2:
        cache.put(key, part)

    # if the sequence info itself is missing, request it
    cache = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
    key = f'txn:{txn_id}'
    if not cache.get(key):
        return Message.prepare(
            Body.prepare(b'', uri=b'txn:' + txn_id),
            MessageType.REQUEST_URI
        )

def publish_txn(txn: Txn):
    msg = Message.prepare(
        Body.prepare(bytes.fromhex(txn.id), uri=b'txn:new'),
        MessageType.NOTIFY_URI
    )
    udpnode.notify('txn', msg)

@udpnode.on((MessageType.NOTIFY_URI, b'txn:new'))
def _receive_new_txn_notification(msg: Message, addr: tuple[str, int]):
    txn_id_bytes = msg.body.content
    if len(txn_id_bytes) != 32:
        return make_error_msg(b'malformed txn id published', uri=msg.body.uri)

    if not Txn.find(txn_id_bytes.hex()):
        # begin pull synchronization
        return Message.prepare(
            Body.prepare(b'', uri=b'txn:' + txn_id_bytes),
            MessageType.REQUEST_URI
        )


# coin scope routers + helpers + handlers
def _route_request_coin_scope(msg: Message, addr: tuple[str, int]):
    if msg.body.uri[:9] == b'coin:list':
        return _get_coin_list(msg, addr)
    elif len(msg.body.uri) == 37: # b'coin:{32-byte id}'
        return _get_coin_seq(msg, addr)
    elif len(msg.body.uri) >= 38: # b'coin:{32-byte id}:{part_idx}'
        return _get_coin_part(msg, addr)
    else:
        return make_error_msg(b'malformed URI for the coin scope', uri=msg.body.uri)

def _get_coin_list(msg: Message, addr: tuple[str, int]):
    """Paginated handler for listing available coin ids."""
    total = Coin.query().count()
    offset, limit = 0, MAX_PART_SIZE // 40 # allow for overhead
    if msg.body.content:
        try:
            params = packify.unpack(msg.body.content)
            type_assert(type(params) is dict)
            offset = params.get('offset', 0)
        except:
            return make_error_msg(b'malformed request', uri=msg.body.uri)

    key = f'coin:ids:{offset}'
    coin_ids = metadata_cache.get(key)
    if coin_ids:
        return make_respond_uri_msg(coin_ids, uri=msg.body.uri)

    sqb = Coin.query().order_by('timestamp', 'asc').select(['id'])
    coin_ids = packify.pack([
        bytes.fromhex(t.id) for t in
        sqb.skip(offset).take(limit)
    ])
    metadata_cache.put(key, coin_ids)
    return make_respond_uri_msg(coin_ids, uri=msg.body.uri)

def _get_coin_seq(msg: Message, addr: tuple[str, int]):
    try:
        seq = get_sequence(Coin, msg.body.uri[:-32].hex(), CacheKind.SEND)
        return make_respond_uri_msg(seq.pack(), uri=msg.body.uri)
    except ValueError:
        return make_not_found_msg.body.uri=msg.body.uri)

def _get_coin_part(msg: Message, addr: tuple[str, int]):
    try:
        # b'coin:{id}:{part_idx}'
        coin_id = msg.body.uri[5:37]
        part_idx = int.from_bytes(msg.body.uri[38:])
        part = get_part(Coin, coin_id, CacheKind.SEND, idx)
        return make_respond_uri_msg(part.pack(), uri=msg.body.uri)
    except ValueError:
        return make_not_found_msg.body.uri=msg.body.uri)

def _route_respond_coin_scope(msg: Message, addr: tuple[str, int]):
    if len(msg.body.uri) == 37: # sequence; b'coin:{id}'
        return _synchronize_coin_seq(msg, addr)
    elif len(msg.body.uri) == 39: # part; b'coin:{id}:{part_idx}'
        return _synchronize_coin_part(msg, addr)

def _synchronize_coin_seq(msg: Message, addr: tuple[str, int]):
    coin_id_bytes = msg.body.uri[:-32]
    coin_id = coin_id_bytes.hex()
    if Coin.find(coin_id):
        return # we already have it, so skip
    try:
        seq = Sequence.unpack(msg.body.content)
    except:
        return make_error_msg(b'malformed Sequence (Coin)', uri=msg.body.uri)
    scz = conf.get('sequence_cache_size', 20)
    cache = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
    key = f'coin:{coin_id}'
    seq2 = cache.get(key)
    if seq2:
        seq = seq2
    else:
        cache.put(key, seq)

    # see if any parts are in the cache and populate to the sequence parts
    pcz = conf.get('parts_cache_size', 1000)
    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
    missing = []
    for i in range(seq.count):
        if seq.has_part(i):
            continue
        key = f'coin:{coin_id}:{i}'
        part = cache.get(key)
        if part:
            try:
                seq.add_part(part)
            except:
                cache.remove(key) # invalid
                missing.append(i)
        else:
            missing.append(i)

    # request up to one missing part and add the rest to synchronization cache
    if missing:
        for m in missing[1:]:
            sync_cache.put(f'coin:{coin_id}:{m}', addr)
        return Message.prepare(
            Body.prepare(
                b'', uri=b'coin:'+coin_id_bytes+':'+missing[0].to_bytes(1, 'big')
            ),
            MessageType.REQUEST_URI
        )

    # otherwise, all parts have been accumulated, so should be able to reconstruct
    try:
        coin = Coin.unpack(seq.reconstruct()
        coin.save()
        publish_coin(coin)
    except:
        ...

def _synchronize_coin_part(msg: Message, addr: tuple[str, int]):
    coin_id = msg.body.uri[4:36]
    if Coin.find(coin_id.hex():
        continue # skip since we already have the record
    part_idx = int.from_bytes(msg.body.uri[37:], 'big')
    try:
        part = Part.unpack(msg.body.content)
        assert part.validate()
        assert part.record_type == 'Coin'
        assert part.record_id == coin_id.hex()
        assert part.idx == part_idx
    except:
        return make_error_msg(b'malformed Part (Coin)', uri=msg.body.uri)
    pcz = conf.get('parts_cache_size', 1000)
    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
    key = f'coin:{coin_id}:{idx}'
    part2 = cache.get(key)
    if not part2:
        cache.put(key, part)

    # if the sequence info itself is missing, request it
    cache = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
    key = f'coin:{coin_id}'
    if not cache.get(key):
        return Message.prepare(
            Body.prepare(b'', uri=b'coin:' + coin_id),
            MessageType.REQUEST_URI
        )

def publish_coin(coin: Coin):
    msg = Message.prepare(
        Body.prepare(bytes.fromhex(coin.id), uri=b'coin:new'),
        MessageType.NOTIFY_URI
    )
    udpnode.notify('coin', msg)

@udpnode.on((MessageType.NOTIFY_URI, b'coin:new'))
def _receive_new_coin_notification(msg: Message, addr: tuple[str, int]):
    coin_id_bytes = msg.body.content
    if len(coin_id_bytes) != 32:
        return make_error_msg(b'malformed coin id published', uri=msg.body.uri)

    if not Coin.find(coin_id_bytes.hex()):
        # begin pull synchronization
        return Message.prepare(
            Body.prepare(b'', uri=b'coin:' + coin_id_bytes),
            MessageType.REQUEST_URI
        )

#@udpnode.on((MessageType.REQUEST_URI, b'nodes'))
#def receive_request_nodes(msg: Message, addr: tuple[str, int]):
#    ...

#@udpnode.on((MessageType.NOTIFY_URI, b'msg'), cipher_plugin=cipher_plugin)
#def receive_chat_notification(msg: Message, addr: tuple[str, int]):
#    ...

#@udpnode.on((MessageType.PUBLISH_URI, b'msg'), cipher_plugin=cipher_plugin)
#def receive_chat_message(msg: Message, addr: tuple[str, int]):
#    ...

#@udpnode.on((MessageType.CREATE_URI, b'msg', cipher_plugin=cipher_plugin))
#def receive_chat_message(msg: Message, addr: tuple[str, int]):
#    ...

