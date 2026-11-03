import pytest

from app.domain.statuses import DeliveryStatus as S
from app.domain.statuses import can_change_delivery_status


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.PENDING, S.COURIER_ASSIGNED),
        (S.PENDING, S.CANCELLED),
        (S.COURIER_ASSIGNED, S.IN_TRANSIT),
        (S.IN_TRANSIT, S.DELIVERED),
    ],
)
def test_allowed_transitions(current, new):
    assert can_change_delivery_status(current, new)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.PENDING, S.DELIVERED),  # can't skip steps
        (S.IN_TRANSIT, S.CANCELLED),  # too late to cancel
        (S.DELIVERED, S.PENDING),  # final status
        (S.CANCELLED, S.COURIER_ASSIGNED),  # final status
        (S.PENDING, S.PENDING),
    ],
)
def test_forbidden_transitions(current, new):
    assert not can_change_delivery_status(current, new)
