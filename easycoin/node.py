from netaio import (
    UDPNode, Peer, Body, Message, MessageType, DefaultPeerPlugin,
    make_error_msg, make_not_found_msg, make_not_permitted_msg,
    make_ok_msg, make_respond_uri_msg
)
from netaio.asymmetric import X25519CipherPlugin
from netaio.node import get_ip
from random import choice as random_choice
from easycoin.UTXOSet import UTXOSet
from easycoin.cache import LRUCache, CacheKind, TimeoutCache
from easycoin.config import get_config_manager
from easycoin.constants import DEFAULT_PORT, MAX_PART_SIZE
from easycoin.cryptoworker import work, submit_txn_job
from easycoin.errors import type_assert, value_assert
from easycoin.models import Coin, Txn, Input, Output
from easycoin.sequence import Part, Sequence, get_sequence, get_part
import asyncio
import os
import packify


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
metadata_cache = TimeoutCache(limit=10, timeout=120.0)
_run_node = True
peers_synched = TimeoutCache(limit=1000, timeout=120.0)
_state_manager = None
_last_peer_list = set()
_last_bootstrap_attempt = 0.0


# main node controls
def stop():
    global _run_node
    _run_node = False

async def run_node(state_manager=None):
    """Run the networking node with optional state manager."""
    global _state_manager, _last_bootstrap_attempt
    if state_manager:
        _state_manager = state_manager

    await udpnode.start()
    await udpnode.manage_peers_automatically(app_id=b'easycoin')
    _connect_to_bootstrap_nodes()
    _last_bootstrap_attempt = asyncio.get_event_loop().time()
    while _run_node:
        await asyncio.sleep(1.0)
        _sync_peer()
        _attempt_sync()
        _monitor_peers()

        current_time = asyncio.get_event_loop().time()
        if current_time - _last_bootstrap_attempt >= 120.0:
            _connect_to_bootstrap_nodes()
            _last_bootstrap_attempt = current_time

def set_node_state_manager(state_manager, logger=None):
    """Set state manager and optionally logger for node."""
    global _state_manager
    _state_manager = state_manager
    
    if logger:
        udpnode.set_logger(logger)

def _get_connected_peers():
    """Get current connected peers list."""
    return [
        {"address": addr[0], "port": addr[1]}
        for addr in udpnode.peer_addrs.keys()
    ]

def _monitor_peers():
    """Monitor peer connections and publish changes."""
    global _last_peer_list
    current_peer_list = set(udpnode.peer_addrs.keys())
    if _state_manager and current_peer_list != _last_peer_list:
        peers_data = _get_connected_peers()
        _state_manager.set("connected_peers", peers_data)
        _last_peer_list = current_peer_list

def _connect_to_bootstrap_nodes():
    """Connect to bootstrap nodes by sending ADVERTISE_PEER messages."""
    bootstrap_nodes = conf.get('bootstrap_nodes')
    if not bootstrap_nodes:
        return

    for node_addr in bootstrap_nodes:
        try:
            parts = node_addr.split(':')
            if len(parts) != 2:
                continue
            addr = parts[0].strip()
            port = int(parts[1].strip())
            peer_addr = (addr, port)

            msg = Message.prepare(
                Body.prepare(
                    DefaultPeerPlugin().pack(udpnode.local_peer),
                    uri=b'easycoin'
                ),
                MessageType.ADVERTISE_PEER
            )
            udpnode.send(msg, peer_addr)
        except (ValueError, IndexError):
            continue

def _sync_peer():
    candidates = set(udpnode.peer_addrs.keys()).difference(set(peers_synched.keys()))
    if not candidates:
        return
    peer = random_choice(list(candidates))
    udpnode.logger.debug(f'_sync_peer choose: {peer}')
    peers_synched.put(peer, {})
    udpnode.send(
        Message.prepare(
            Body.prepare(b'', uri=b'txns'),
            MessageType.REQUEST_URI
        ),
        peer
    )

def _attempt_sync():
    # choose the next item that needs to be synchronized
    item = sync_cache.peak_last()

    # do nothing if there is nothing to do
    if not item:
        return

    # if the record has been acquired, remove it from the sync cache
    key, addrs = item
    udpnode.logger.debug(f'_attempt_sync: {key=}, {addrs=}')
    if len(key.split(':')) == 2:
        scope, record_id = key.split(':')
        idx = None
    elif len(key.split(':')) == 3:
        scope, record_id, idx = key.split(':')
        idx = int(idx)
    else:
        udpnode.logger.warn('malformed sync cache data')
        return # malformed data
    if scope == 'txn' and Txn.find(record_id):
        return sync_cache.pop(key)
    elif scope == 'coin' and Coin.find(record_id):
        return sync_cache.pop(key)

    # request it from each node that should have it
    if idx:
        uri = b':'.join([
            scope.encode(), bytes.fromhex(record_id), idx.to_bytes(1, 'big')
        ])
    else:
        uri = b':'.join([scope.encode(), bytes.fromhex(record_id)])
    for addr in addrs:
        udpnode.send(
            Message.prepare(Body.prepare(b'', uri=uri), MessageType.REQUEST_URI),
            addr
        )


# log error messages
@udpnode.on(MessageType.NOT_FOUND)
def _not_found(msg: Message, addr: tuple[str, int]):
    udpnode.logger.warning(f'NOT_FOUND encountered from {addr}')

@udpnode.on(MessageType.ERROR)
def _error(msg: Message, addr: tuple[str, int]):
    udpnode.logger.warning(f'ERROR encountered from {addr}: {msg.body.content}')

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
    meta['cols'] = {}
    for c in cols:
        meta['cols'][c] = {
            'min': model.query().order_by(c, 'asc').first().data.get(c, None),
            'max': model.query().order_by(c, 'desc').first().data.get(c, None),
        }
    meta = packify.pack(meta)
    metadata_cache.put(model.__name__, meta)
    return meta

@udpnode.on((MessageType.REQUEST_URI, b'txns'))
def _respond_with_txns_metadata(msg: Message, addr: tuple[str, int]):
    return make_respond_uri_msg(_get_metadata(Txn, ['timestamp']), msg.body.uri)

@udpnode.on((MessageType.RESPOND_URI, b'txns'))
def _pull_txn_ids_from_peer(msg: Message, addr: tuple[str, int]):
    try:
        info = packify.unpack(msg.body.content)
        type_assert(type(info) is dict)
        udpnode.logger.debug(f'_pull_txn_ids_from_peer: {info}')
    except:
        udpnode.logger.warn('failed to parse txns metadata from peer')
        return
    data = peers_synched.get(addr) or {}
    data['count'] = info.get('count', 0)
    data['cols'] = info.get('cols', {})
    peers_synched.put(addr, data)

    if data['count'] == 0:
        return

    # request first page of ids
    return Message.prepare(
        Body.prepare(
            packify.pack({}), uri=b'txn:list'
        ),
        MessageType.REQUEST_URI
    )

#@udpnode.on((MessageType.REQUEST_URI, b'coins'))
#def _respond_with_coins_metadata(msg: Message, addr: tuple[str, int]):
#    return make_respond_uri_msg(_get_metadata(Coin, ['timestamp']), msg.body.uri)

# main request router
@udpnode.on(MessageType.REQUEST_URI)
def route_request(msg: Message, addr: tuple[str, int]):
    if msg.body.uri[:4] == b'txn:':
        return _route_request_txn_scope(msg, addr)
#    elif msg.body.uri[:5] == b'coin:'
#        return _route_request_coin_scope(msg, addr)
    return make_not_found_msg(uri=msg.body.uri)

# main respond router (pull synchronizer)
@udpnode.on(MessageType.RESPOND_URI)
def route_respond(msg: Message, addr: tuple[str, int]):
    if msg.body.uri[:4] == b'txn:':
        return _route_respond_txn_scope(msg, addr)
    elif msg.body.uri[:5] == b'coin:':
        return _route_respond_coin_scope(msg, addr)
    return make_not_found_msg(uri=msg.body.uri)

# txn scope routers + handlers + helpers
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

def _route_request_txn_scope(msg: Message, addr: tuple[str, int]):
    udpnode.logger.debug(f'_route_request_txn_scope: {msg.body.uri}')
    if msg.body.uri == b'txn:list':
        return _get_txn_list(msg, addr)
    elif len(msg.body.uri) == 36: # b'txn:{32-byte id}'
        udpnode.logger.debug(f'_route_request_txn_scope: _get_txn_seq')
        return _get_txn_seq(msg, addr)
    elif len(msg.body.uri) == 38: # b'txn:{32-byte id}:{idx}'
        udpnode.logger.debug(f'_route_request_txn_scope: _get_txn_part')
        return _get_txn_part(msg, addr)
    else:
        udpnode.logger.debug(f'_route_request_txn_scope: malformed URI')
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
        txn_id = msg.body.uri[-32:].hex()
        udpnode.logger.debug(f'_get_txn_seq: {txn_id=}')
        seq = get_sequence(Txn, txn_id, CacheKind.SEND)
        return make_respond_uri_msg(seq.pack(), uri=msg.body.uri)
    except ValueError:
        udpnode.logger.warn(f'_get_txn_seq: ValueError - sending NOT_FOUND')
        return make_not_found_msg(uri=msg.body.uri)

def _get_txn_part(msg: Message, addr: tuple[str, int]):
    try:
        # b'txn:{id}:{idx}'
        txn_id = msg.body.uri[4:36]
        idx = int.from_bytes(msg.body.uri[37:], 'big')
        part = get_part(Txn, txn_id, CacheKind.SEND, idx)
        return make_respond_uri_msg(part.pack(), uri=msg.body.uri)
    except ValueError:
        return make_not_found_msg(uri=msg.body.uri)

def _route_respond_txn_scope(msg: Message, addr: tuple[str, int]):
    if msg.body.uri == b'txn:list':
        return _handle_txn_ids_page(msg, addr)
    elif len(msg.body.uri) == 36: # sequence; b'txn:{id}'
        return _synchronize_txn_seq(msg, addr)
    elif len(msg.body.uri) == 38: # part; b'txn:{id}:{idx}'
        return _synchronize_txn_part(msg, addr)

def _handle_txn_ids_page(msg: Message, addr: tuple[str, int]):
    try:
        txn_ids = packify.unpack(msg.body.content)
        type_assert(type(txn_ids) is list)
        udpnode.logger.debug(f'_handle_txn_ids_page: got {len(txn_ids)} txn ids')
    except:
        udpnode.logger.warn('failed to parse txn:list page from peer')
        return

    # queue up for synchronization any missing txns
    txn_ids = [t.hex() for t in txn_ids]
    sqb = Txn.query().is_in('id', txn_ids)
    if sqb.count() < len(txn_ids):
        already_have = [t.id for t in sqb.select(['id']).get()]
        missing = [tid in txn_ids if tid not in already_have]
        for txn_id in missing:
            key = f'txn:{txn_id}'
            sync_cache.put(key, {addr})

    # request next page if we can and should
    info = peers_synched.get(addr)
    if not info:
        return
    offset = info.get('offset', 0) + len(txn_ids)
    info['offset'] = offset
    peers_synched.put(addr, info)
    if offset < info.get('count', 0):
        udpnode.logger.debug(f'_handle_txn_ids_page: request next page with {offset=}')
        return Message.prepare(
            Body.prepare(
                packify.pack({'offset': offset}), uri=b'txn:list'
            ),
            MessageType.REQUEST_URI
        )

def _synchronize_txn_seq(msg: Message, addr: tuple[str, int]):
    txn_id_bytes = msg.body.uri[-32:]
    txn_id = txn_id_bytes.hex()
    if Txn.find(txn_id):
        return # we already have it, so skip
    try:
        seq = Sequence.unpack(msg.body.content)
    except BaseException as e:
        udpnode.logger.warn(f'_synchronize_coin_seq: {e}')
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
        addrs = {addr}
        for i in missing[1:]:
            key = f'txn:{txn_id}:{i}'
            m = sync_cache.get(key)
            if m:
                addrs.update(m)
            sync_cache.put(key, addrs)
        return Message.prepare(
            Body.prepare(
                b'', uri=b'txn:'+txn_id_bytes+':'+missing[0].to_bytes(1, 'big')
            ),
            MessageType.REQUEST_URI
        )

    # otherwise, all parts have been accumulated, so should be able to reconstruct
    try:
        txn = Txn.unpack(seq.reconstruct())
        if not txn.validate(reload=False):
            udpnode.logger.warn(
                f'received txn failed validation: {txn.id}; ignoring'
            )
            return
        utxos = UTXOSet()
        if not utxos.can_apply(txn):
            udpnode.logger.warn(
                f'received txn could not be applied to the UTXOSet: {txn.id}; '
                'ignoring'
            )
            return
        txn.save()
        coins = [*txn.inputs, *txn.outputs]
        for c in coins:
            try:
                c.save()
            except:
                udpnode.logger.warn(
                    f'coin in txn ({txn.id}) could not be saved: {c.id}'
                )
        utxos.apply(txn, {c.id: c for c in coins})
        publish_txn(txn)
        if _state_manager:
            _state_manager.publish("append_new_txn", txn.id)
    except:
        udpnode.logger.warn(
            'malicious or duplicate Txn data encountered; dropped'
        )

def _synchronize_txn_part(msg: Message, addr: tuple[str, int]):
    txn_id_bytes = msg.body.uri[4:36]
    txn_id = txn_id_bytes.hex()
    if Txn.find(txn_id):
        return # skip since we already have the record
    idx = int.from_bytes(msg.body.uri[37:], 'big')
    try:
        part = Part.unpack(msg.body.content)
        assert part.validate()
        assert part.record_type == 'Txn'
        assert part.record_id == txn_id
        assert part.idx == idx
    except:
        return make_error_msg(b'malformed Part (Txn)', uri=msg.body.uri)
    pcz = conf.get('parts_cache_size', 1000)
    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
    key = f'txn:{txn_id}:{idx}'
    part2 = cache.get(key)
    if not part2:
        cache.put(key, part)

    # remove from sync cache
    sync_cache.pop(key)

    # try to add to the seqence
    scz = conf.get('sequence_cache_size', 20)
    cache2 = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
    key2 = f'txn:{txn_id}'
    seq = cache2.get(key2)
    # if the sequence info itself is missing, request it
    if not seq:
        return Message.prepare(
            Body.prepare(b'', uri=b'txn:' + txn_id),
            MessageType.REQUEST_URI
        )
    try:
        seq.add_part(part)
    except:
        cache.remove(key) # invalid

    # see if any parts are in the cache and populate to the sequence parts
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
        addrs = {addr}
        for i in missing[1:]:
            key = f'txn:{txn_id}:{i}'
            m = sync_cache.get(key)
            if m:
                addrs.update(m)
            sync_cache.put(key, addrs)
        return Message.prepare(
            Body.prepare(
                b'', uri=b'txn:'+txn_id_bytes+':'+missing[0].to_bytes(1, 'big')
            ),
            MessageType.REQUEST_URI
        )

    # otherwise, all parts have been accumulated, so should be able to reconstruct
    try:
        txn = Txn.unpack(seq.reconstruct())
        if not txn.validate(reload=False):
            udpnode.logger.warn(
                f'received txn failed validation: {txn.id}; ignoring'
            )
            return
        utxos = UTXOSet()
        if not utxos.can_apply(txn):
            udpnode.logger.warn(
                f'received txn could not be applied to the UTXOSet: {txn.id}; '
                'ignoring'
            )
            return
        txn.save()
        coins = [*txn.inputs, *txn.outputs]
        for c in coins:
            try:
                c.save()
            except:
                udpnode.logger.warn(
                    f'coin in txn ({txn.id}) could not be saved: {c.id}'
                )
        utxos.apply(txn, {c.id: c for c in coins})
        publish_txn(txn)
        if _state_manager:
            _state_manager.publish("append_new_txn", txn.id)
    except:
        udpnode.logger.warn(
            'malicious or duplicate Txn data encountered; dropped'
        )


# coin scope routers + helpers + handlers
#def _route_request_coin_scope(msg: Message, addr: tuple[str, int]):
#    if msg.body.uri[:9] == b'coin:list':
#        return _get_coin_list(msg, addr)
#    elif len(msg.body.uri) == 37: # b'coin:{32-byte id}'
#        return _get_coin_seq(msg, addr)
#    elif len(msg.body.uri) >= 38: # b'coin:{32-byte id}:{idx}'
#        return _get_coin_part(msg, addr)
#    else:
#        return make_error_msg(b'malformed URI for the coin scope', uri=msg.body.uri)
#
#def _get_coin_list(msg: Message, addr: tuple[str, int]):
#    """Paginated handler for listing available coin ids."""
#    total = Coin.query().count()
#    offset, limit = 0, MAX_PART_SIZE // 40 # allow for overhead
#    if msg.body.content:
#        try:
#            params = packify.unpack(msg.body.content)
#            type_assert(type(params) is dict)
#            offset = params.get('offset', 0)
#        except:
#            return make_error_msg(b'malformed request', uri=msg.body.uri)
#
#    key = f'coin:ids:{offset}'
#    coin_ids = metadata_cache.get(key)
#    if coin_ids:
#        return make_respond_uri_msg(coin_ids, uri=msg.body.uri)
#
#    sqb = Coin.query().order_by('timestamp', 'asc').select(['id'])
#    coin_ids = packify.pack([
#        bytes.fromhex(t.id) for t in
#        sqb.skip(offset).take(limit)
#    ])
#    metadata_cache.put(key, coin_ids)
#    return make_respond_uri_msg(coin_ids, uri=msg.body.uri)
#
#def _get_coin_seq(msg: Message, addr: tuple[str, int]):
#    try:
#        seq = get_sequence(Coin, msg.body.uri[-32:].hex(), CacheKind.SEND)
#        return make_respond_uri_msg(seq.pack(), uri=msg.body.uri)
#    except ValueError:
#        return make_not_found_msg(uri=msg.body.uri)
#
#def _get_coin_part(msg: Message, addr: tuple[str, int]):
#    try:
#        # b'coin:{id}:{idx}'
#        coin_id = msg.body.uri[5:37]
#        idx = int.from_bytes(msg.body.uri[38:])
#        part = get_part(Coin, coin_id, CacheKind.SEND, idx)
#        return make_respond_uri_msg(part.pack(), uri=msg.body.uri)
#    except ValueError:
#        return make_not_found_msg(uri=msg.body.uri)
#
#def _route_respond_coin_scope(msg: Message, addr: tuple[str, int]):
#    if len(msg.body.uri) == 37: # sequence; b'coin:{id}'
#        return _synchronize_coin_seq(msg, addr)
#    elif len(msg.body.uri) == 39: # part; b'coin:{id}:{idx}'
#        return _synchronize_coin_part(msg, addr)
#
#def _synchronize_coin_seq(msg: Message, addr: tuple[str, int]):
#    coin_id_bytes = msg.body.uri[-32:]
#    coin_id = coin_id_bytes.hex()
#    if Coin.find(coin_id):
#        return # we already have it, so skip
#    try:
#        seq = Sequence.unpack(msg.body.content)
#    except:
#        return make_error_msg(b'malformed Sequence (Coin)', uri=msg.body.uri)
#    scz = conf.get('sequence_cache_size', 20)
#    cache = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
#    key = f'coin:{coin_id}'
#    seq2 = cache.get(key)
#    if seq2:
#        seq = seq2
#    else:
#        cache.put(key, seq)
#
#    # see if any parts are in the cache and populate to the sequence parts
#    pcz = conf.get('parts_cache_size', 1000)
#    cache2 = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
#    missing = []
#    for i in range(seq.count):
#        if seq.has_part(i):
#            continue
#        key = f'coin:{coin_id}:{i}'
#        part = cache2.get(key)
#        if part:
#            try:
#                seq.add_part(part)
#            except:
#                cache2.remove(key) # invalid
#                missing.append(i)
#        else:
#            missing.append(i)
#
#    # request up to one missing part and add the rest to synchronization cache
#    if missing:
#        addrs = {addr}
#        for i in missing[1:]:
#            key = f'coin:{coin_id}:{i}'
#            m = sync_cache.get(key)
#            if m:
#                addrs.update(m)
#            sync_cache.put(key, addrs)
#        return Message.prepare(
#            Body.prepare(
#                b'', uri=b'coin:'+coin_id_bytes+':'+missing[0].to_bytes(1, 'big')
#            ),
#            MessageType.REQUEST_URI
#        )
#
#    # otherwise, all parts have been accumulated, so should be able to reconstruct
#    try:
#        coin = Coin.unpack(seq.reconstruct())
#        coin.save()
#        publish_coin(coin)
#    except:
#        udpnode.logger.warn(
#            'malicious or duplicate Coin data encountered; dropped'
#        )
#
#def _synchronize_coin_part(msg: Message, addr: tuple[str, int]):
#    coin_id_bytes = msg.body.uri[5:37]
#    coin_id = coin_id_bytes.hex()
#    if Coin.find(coin_id):
#        return # skip since we already have the record
#    idx = int.from_bytes(msg.body.uri[38:], 'big')
#    try:
#        part = Part.unpack(msg.body.content)
#        assert part.validate()
#        assert part.record_type == 'Coin'
#        assert part.record_id == coin_id
#        assert part.idx == idx
#    except:
#        return make_error_msg(b'malformed Part (Coin)', uri=msg.body.uri)
#    pcz = conf.get('parts_cache_size', 1000)
#    cache = LRUCache.get_instance('parts', CacheKind.RECEIVE, pcz)
#    key = f'coin:{coin_id}:{idx}'
#    part2 = cache.get(key)
#    if not part2:
#        cache.put(key, part)
#
#    # remove from sync cache
#    sync_cache.pop(key)
#
#    # try to add to the seqence
#    scz = conf.get('sequence_cache_size', 20)
#    cache2 = LRUCache.get_instance('sequences', CacheKind.RECEIVE, scz)
#    key2 = f'coin:{coin_id}'
#    seq = cache2.get(key2)
#    # if the sequence info itself is missing, request it
#    if not seq:
#        return Message.prepare(
#            Body.prepare(b'', uri=b'coin:' + coin_id),
#            MessageType.REQUEST_URI
#        )
#    try:
#        seq.add_part(part)
#    except:
#        cache.remove(key) # invalid
#
#    # see if any parts are in the cache and populate to the sequence parts
#    missing = []
#    for i in range(seq.count):
#        if seq.has_part(i):
#            continue
#        key = f'coin:{coin_id}:{i}'
#        part = cache.get(key)
#        if part:
#            try:
#                seq.add_part(part)
#            except:
#                cache.remove(key) # invalid
#                missing.append(i)
#        else:
#            missing.append(i)
#
#    # request up to one missing part and add the rest to synchronization cache
#    if missing:
#        addrs = {addr}
#        for i in missing[1:]:
#            key = f'coin:{coin_id}:{i}'
#            m = sync_cache.get(key)
#            if m:
#                addrs.update(m)
#            sync_cache.put(key, addrs)
#        return Message.prepare(
#            Body.prepare(
#                b'', uri=b'coin:'+coin_id_bytes+':'+missing[0].to_bytes(1, 'big')
#            ),
#            MessageType.REQUEST_URI
#        )
#
#    # otherwise, all parts have been accumulated, so should be able to reconstruct
#    try:
#        coin = Coin.unpack(seq.reconstruct())
#        coin.save()
#        publish_coin(coin)
#    except:
#        ...
#
#def publish_coin(coin: Coin):
#    msg = Message.prepare(
#        Body.prepare(bytes.fromhex(coin.id), uri=b'coin:new'),
#        MessageType.NOTIFY_URI
#    )
#    udpnode.notify('coin', msg)
#
#@udpnode.on((MessageType.NOTIFY_URI, b'coin:new'))
#def _receive_new_coin_notification(msg: Message, addr: tuple[str, int]):
#    coin_id_bytes = msg.body.content
#    if len(coin_id_bytes) != 32:
#        return make_error_msg(b'malformed coin id published', uri=msg.body.uri)
#
#    if not Coin.find(coin_id_bytes.hex()):
#        # begin pull synchronization
#        return Message.prepare(
#            Body.prepare(b'', uri=b'coin:' + coin_id_bytes),
#            MessageType.REQUEST_URI
#        )

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

