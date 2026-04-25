# Transport tests — Phase 2. Placeholder.
import pytest
from thelmic.transport import Transport
from thelmic.bank_generator import Bank


def test_transport_not_yet_implemented():
    t = Transport()
    with pytest.raises(NotImplementedError):
        t.queue_bank(Bank(bank_index=0))
