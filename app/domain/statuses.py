from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    CREATED = "created"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    COURIER_ASSIGNED = "courier_assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# A tiny state machine: which delivery status can follow which.
DELIVERY_TRANSITIONS: dict[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.PENDING: frozenset({DeliveryStatus.COURIER_ASSIGNED, DeliveryStatus.CANCELLED}),
    DeliveryStatus.COURIER_ASSIGNED: frozenset({DeliveryStatus.IN_TRANSIT}),
    DeliveryStatus.IN_TRANSIT: frozenset({DeliveryStatus.DELIVERED}),
    DeliveryStatus.DELIVERED: frozenset(),
    DeliveryStatus.CANCELLED: frozenset(),
}


def can_change_delivery_status(current: DeliveryStatus, new: DeliveryStatus) -> bool:
    return new in DELIVERY_TRANSITIONS[current]
