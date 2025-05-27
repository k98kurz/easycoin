from .models import Coin, Input, Output
from dataclasses import dataclass, field
from typing import Protocol


class TxnProtocol(Protocol):
    @property
    def input_ids(self) -> list[str|bytes]:
        ...

    @property
    def output_ids(self) -> list[str|bytes]:
        ...


@dataclass
class UTXOSet:
    add_outputs: set = field(default_factory=set)
    sub_outputs: set = field(default_factory=set)
    add_inputs: set = field(default_factory=set)
    sub_inputs: set = field(default_factory=set)

    def copy(self) -> 'UTXOSet':
        """Build a copy of the current UTXOSet with no changes."""
        return UTXOSet(
            self.add_outputs.copy(),
            self.sub_outputs.copy(),
            self.add_inputs.copy(),
            self.sub_inputs.copy(),
        )

    def before(self, txn: TxnProtocol) -> 'UTXOSet':
        """Build a copy of the current UTXOSet that has ephemerally
            reversed the given transaction.
        """
        u = self.copy()
        for iid in txn.input_ids:
            u.add_outputs.add(iid)
            u.sub_inputs.add(iid)
        for oid in txn.output_ids:
            u.sub_outputs.add(oid)
        return u

    def after(self, txn: TxnProtocol) -> 'UTXOSet':
        """Build a copy of the current UTXOSet that has ephemerally
            applied the given transaction.
        """
        u = self.copy()
        for iid in txn.input_ids:
            u.add_inputs.add(iid)
            u.sub_outputs.add(iid)
        for oid in txn.output_ids:
            u.add_outputs.add(oid)
            u.sub_inputs.add(oid)
        return u

    def can_apply(self, txn: TxnProtocol, debug: bool = False) -> bool:
        """Determine if a txn can be applied to the current UTXOSet.
            This returns False if a `txn.input_ids[i]` is not an unspent
            output or if a `txn.output_ids[i]` is already an input
            (spent); otherwise returns True. This means that any number
            of valid inputs can be burned to fund an already-funded
            output -- if one of the `txn.output_ids` has already been
            added to the UTXOSet and a new transaction attempts to spend
            another UTXO to fund it, those EC⁻¹ in the input will be
            burned. First checks ephemeral UTXOSet changes, then queries
            the database.
        """
        # check ephemeral data first
        for iid in txn.input_ids:
            if iid in self.sub_outputs or iid in self.add_inputs:
                print('line 72') if debug else ''
                return False
        for oid in txn.output_ids:
            if oid in self.add_inputs:
                print('line 76') if debug else ''

        # first database check: ensure non-ephemeral inputs have not been spent
        sub_i = {iid for iid in txn.input_ids if iid in self.sub_inputs}
        add_o = {iid for iid in txn.input_ids if iid in self.add_outputs}
        both = sub_i.union(add_o)

        if len(set(txn.input_ids).difference(both)) and Input.query().is_in(
            'id',
            list(set(txn.input_ids).difference(both))
        ).count():
            print('line 87') if debug else ''
            return False

        # second database check: ensure inputs are unspent outputs
        if txn.input_ids:
            real_outputs = [o.id for o in Output.query().is_in('id', txn.input_ids).get()]
        else:
            real_outputs = []
        for iid in txn.input_ids:
            if iid not in real_outputs and iid not in self.add_outputs:
                print(f'line 97; {iid=}') if debug else ''
                return False

        return True

    def can_reverse(self, txn: TxnProtocol, debug: bool = False) -> bool:
        """Determine if a txn can be reversed in the current UTXOSet.
            This returns False if a `txn.output_ids[i]` is not an unspent
            output or if a `txn.input_ids[i]` is not an input (spent);
            otherwise returns True. First checks ephemeral UTXOSet
            changes, then queries the database.
        """
        # check ephemeral data first
        for oid in txn.output_ids:
            if oid in self.add_inputs or oid in self.sub_outputs:
                print('line 112') if debug else ''
                return False
        for iid in txn.input_ids:
            if iid in self.add_outputs:
                print('line 116') if debug else ''

        sub_o = {oid for oid in txn.output_ids if oid in self.sub_outputs}
        add_i = {oid for oid in txn.output_ids if oid in self.add_inputs}
        both = sub_o.union(add_i)

        # check database on non-ephemeral outputs: ensure they have not been spent
        if len(set(txn.output_ids).difference(both)) and Input.query().is_in(
            'id',
            list(set(txn.output_ids).difference(both))
        ).count():
            print('line 126') if debug else ''
            return False

        return True

    def apply(self, txn: TxnProtocol, coins: dict[str, Coin] = {}):
        """Attempt to apply the transaction, persisting the changes to
            the database. Raises `ValueError` if it cannot be applied or
            if there is ephemeral data in the `UTXOSet` instance.
        """
        ephemeral = len(self.sub_outputs) + len(self.add_outputs)
        ephemeral = len(self.sub_inputs) + len(self.add_inputs)
        if ephemeral:
            raise ValueError('txn cannot be applied to an ephemeral UTXOSet')
        if not self.can_apply(txn):
            raise ValueError('txn cannot be applied')

        # delete spent outputs and mark them as inputs; 
        if txn.input_ids:
            Output.query().is_in('id', txn.input_ids).delete()
            inputs = []
            for i in txn.input_ids:
                if i in coins:
                    inputs.append(Input.from_coin(coins[i]).data)
                else:
                    inputs.append({'id': i})
            Input.insert_many(inputs)

        # create new outputs
        if txn.output_ids:
            existing = [o.id for o in Output.query().is_in('id', txn.output_ids).get()]
            outputs = []
            for i in [i for i in txn.output_ids if i not in existing]:
                if i in coins:
                    outputs.append(Output.from_coin(coins[i]).data)
                else:
                    outputs.append({'id': i})
            Output.insert_many(outputs)

    def reverse(self, txn: TxnProtocol, coins: dict[str, Coin] = {}):
        """Attempt to reverse (or un-apply) the transaction, persisting
            the changes to the database. Raises `ValueError` if it
            cannot be reversed or if there is ephemeral data in the
            `UTXOSet` instance.
        """
        ephemeral = len(self.sub_outputs) + len(self.add_outputs)
        ephemeral = len(self.sub_inputs) + len(self.add_inputs)
        if ephemeral:
            raise ValueError('txn cannot be reversed in an ephemeral UTXOSet')
        if not self.can_reverse(txn):
            raise ValueError('txn cannot be reversed')

        # delete outputs
        if txn.output_ids:
            Output.query().is_in('id', txn.output_ids).delete()

        # undelete inputs -- make them into outputs
        if txn.input_ids:
            Input.query().is_in('id', txn.input_ids).delete()
            existing = [o.id for o in Output.query().is_in('id', txn.input_ids).get()]
            outputs = []
            for i in [i for i in txn.input_ids if i not in existing]:
                if i in coins:
                    outputs.append(Output.from_coin(coins[i]).data)
                else:
                    outputs.append({'id': i})
            Output.insert_many(outputs)

