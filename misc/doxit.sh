#!/bin/bash

autodox easycoin.cache -exclude_name=OrderedDict,Enum,Any,Hashable,annotations > docs/cache.md
autodox easycoin.config -exclude_name=Any,lru_cache,Callable,get_config,set_mining_pool_size > docs/config.md
autodox easycoin.cryptoworker -exclude_name=Txn,Coin,ProcessPoolExecutor,Enum,Script,dataclass,field,annotations,deque > docs/cryptoworker.md
autodox easycoin.gameset -exclude_name=StringIO,ZipFile,SqlModel,Coin,Txn,Input,Output,makedirs,copy2,rmtree,mkdtemp,isfile,isdir,type_assert,value_assert,publish_migrations,automigrate,listdir,remove,rmdir,sha256,time,ZIP_DEFLATED > docs/gameset.md
autodox easycoin.helpers -exclude_name=datetime > docs/helpers.md
autodox easycoin.models -exclude_name=contains,within,belongs_to,has_many,has_one,Callable > docs/models.md
autodox easycoin.sequence -exclude_name=Tree,SqlModel,LRUCache,CacheKind,dataclass,field,annotations,get_config_manager > docs/sequence.md
autodox easycoin.state -exclude_name=datetime,Any,dataclass,field,lru_cache,Callable > docs/state.md
autodox easycoin.UTXOSet -exclude_name=Coin,Input,Output,Txn,Protocol,dataclass,field,annotations > docs/utxoset.md
