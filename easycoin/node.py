from collections import deque
from netaio import UDPNode, Peer, Body, Message, MessageType, DefaultPeerPlugin
from netaio.asymmetric import X25519CipherPlugin
from netaio.node import get_ip
from easycoin.constants import DEFAULT_PORT
from easycoin.cryptoworker import work, submit_txn_job
from easycoin.models import Coin, Txn, Input, Output
import os


seed = os.urandom(32)
cipher_plugin = X25519CipherPlugin({
    'seed': seed,
})
local_peer = Peer(
    addrs={(get_ip(), DEFAULT_PORT)}, id=bytes(cipher_plugin.vkey),
    data=DefaultPeerPlugin().encode_data({
        "pubkey": bytes(cipher_plugin.pubk),
        "vkey": bytes(cipher_plugin.vkey),
    })
)
udpnode = UDPNode(port=DEFAULT_PORT)


@udpnode.on((MessageType.REQUEST_URI, b'nodes'))
async def receive_request_nodes(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.NOTIFY_URI, b'msg'), cipher_plugin=cipher_plugin)
async def receive_chat_notification(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.PUBLISH_URI, b'msg'), cipher_plugin=cipher_plugin)
async def receive_chat_message(msg: Message, addr: tuple[str, int]):
    ...

#@udpnode.on((MessageType.CREATE_URI, b'msg', cipher_plugin=cipher_plugin))
#async def receive_chat_message(msg: Message, addr: tuple[str, int]):
#    ...

@udpnode.on((MessageType.REQUEST_URI, b'coin'))
async def receive_request_coin(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.RESPOND_URI, b'coin'))
async def receive_respond_coin(msg: MessageType, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.REQUEST_URI, b'txn'))
async def receive_request_txn(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.RESPOND_URI, b'txn'))
async def receive_respond_txn(msg: MessageType, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.NOTIFY_URI, b'txn'))
async def receive_txn_notification(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.PUBLISH_URI, b'txn'))
async def receive_txn_publication(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.REQUEST_URI, b'txo'))
async def receive_txo_query(msg: Message, addr: tuple[str, int]):
    ...

@udpnode.on((MessageType.RESPOND_URI, b'txo'))
async def receive_txo_answer(msg: Message, addr: tuple[str, int]):
    ...




