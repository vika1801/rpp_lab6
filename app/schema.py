import logging
import os
from enum import Enum
from datetime import datetime
from decimal import Decimal
from typing import AsyncGenerator

import strawberry
from graphql import GraphQLError
from strawberry.dataloader import DataLoader
from strawberry.types import Info

from app import db, events, services

log = logging.getLogger(__name__)


class OrderStatusValue(Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


OrderStatus = strawberry.enum(OrderStatusValue)
FINAL_STATES = {"DELIVERED", "CANCELLED"}
USE_DATALOADER = os.getenv("USE_DATALOADER", "true").lower() == "true"


@strawberry.type
class Restaurant:
    id: strawberry.ID
    name: str
    address: str

    @strawberry.field
    async def dishes(self, info: Info) -> list["Dish"]:
        rows = await db.list_dishes(int(self.id))
        return [to_dish(row) for row in rows]


@strawberry.type
class Dish:
    id: strawberry.ID
    name: str
    price: Decimal
    restaurant_id: strawberry.Private[int]

    @strawberry.field
    async def restaurant(self, info: Info) -> Restaurant:
        if USE_DATALOADER:
            row = await info.context["restaurants"].load(self.restaurant_id)
        else:
            row = await db.get_restaurant(self.restaurant_id)
        return to_restaurant(row)


@strawberry.type
class OrderItem:
    quantity: int
    price: Decimal
    dish_id: strawberry.Private[int]

    @strawberry.field
    def amount(self) -> Decimal:
        return self.price * self.quantity

    @strawberry.field
    async def dish(self, info: Info) -> Dish:
        if USE_DATALOADER:
            row = await info.context["dishes"].load(self.dish_id)
        else:
            row = await db.get_dish(self.dish_id)
        return to_dish(row)


@strawberry.type
class Order:
    id: strawberry.ID
    status: OrderStatus
    total: Decimal
    created_at: datetime
    customer_name: str
    delivery_address: str
    cancel_reason: str | None
    restaurant_id: strawberry.Private[int]

    @strawberry.field
    async def restaurant(self, info: Info) -> Restaurant:
        if USE_DATALOADER:
            row = await info.context["restaurants"].load(self.restaurant_id)
        else:
            row = await db.get_restaurant(self.restaurant_id)
        return to_restaurant(row)

    @strawberry.field
    async def items(self, info: Info) -> list[OrderItem]:
        if USE_DATALOADER:
            rows = await info.context["items"].load(int(self.id))
        else:
            rows = await db.get_items(int(self.id))
        return [to_item(row) for row in rows]


def to_restaurant(row) -> Restaurant:
    return Restaurant(id=strawberry.ID(str(row.id)), name=row.name, address=row.address)


def to_dish(row) -> Dish:
    return Dish(
        id=strawberry.ID(str(row.id)), name=row.name,
        price=Decimal(row.price), restaurant_id=row.restaurant_id
    )


def to_item(row) -> OrderItem:
    return OrderItem(
        quantity=row.quantity, price=Decimal(row.price), dish_id=row.dish_id
    )


def to_order(row) -> Order:
    return Order(
        id=strawberry.ID(str(row.id)), status=row.status, total=Decimal(row.total),
        created_at=row.created_at, customer_name=row.customer_name,
        delivery_address=row.delivery_address, cancel_reason=row.cancel_reason,
        restaurant_id=row.restaurant_id
    )


@strawberry.input
class CreateOrderItemInput:
    dish_id: strawberry.ID
    quantity: int


@strawberry.input
class CreateOrderInput:
    restaurant_id: strawberry.ID
    customer_name: str
    delivery_address: str
    items: list[CreateOrderItemInput]


async def load_restaurants(ids: list[int]):
    found = await db.get_restaurants(ids)
    return [found.get(key) for key in ids]


async def load_dishes(ids: list[int]):
    found = await db.get_dishes(ids)
    return [found.get(key) for key in ids]


async def load_items(order_ids: list[int]):
    found = await db.get_items_by_orders(order_ids)
    return [found.get(key, []) for key in order_ids]


async def get_context():
    return {
        "restaurants": DataLoader(load_fn=load_restaurants),
        "dishes": DataLoader(load_fn=load_dishes),
        "items": DataLoader(load_fn=load_items),
    }


async def call_service(operation):
    try:
        return await operation
    except services.NotFound as exc:
        raise GraphQLError(str(exc), extensions={"code": "NOT_FOUND"})
    except services.TransitionNotAllowed as exc:
        raise GraphQLError(str(exc), extensions={"code": "TRANSITION_NOT_ALLOWED"})
    except services.OrderValidationError as exc:
        raise GraphQLError(str(exc), extensions={"code": "VALIDATION_ERROR"})
    except Exception:
        log.exception("Внутренняя ошибка приложения")
        raise GraphQLError("Internal error", extensions={"code": "INTERNAL_ERROR"})


@strawberry.type
class Query:
    @strawberry.field
    async def order(self, id: strawberry.ID) -> Order | None:
        row = await db.get_order(int(id))
        return to_order(row) if row else None

    @strawberry.field
    async def orders(self, status: OrderStatus | None = None) -> list[Order]:
        value = status.value if status is not None else None
        return [to_order(row) for row in await db.list_orders(value)]

    @strawberry.field
    async def restaurants(self) -> list[Restaurant]:
        rows = await db.list_restaurants()
        return [to_restaurant(row) for row in rows]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_order(self, input: CreateOrderInput) -> Order | None:
        data = [{"dish_id": int(x.dish_id), "quantity": x.quantity} for x in input.items]
        row = await call_service(services.create_order(
            int(input.restaurant_id), input.customer_name, input.delivery_address, data
        ))
        return to_order(row)

    @strawberry.mutation
    async def accept_order(self, id: strawberry.ID) -> Order | None:
        return to_order(await call_service(services.accept(int(id))))

    @strawberry.mutation
    async def mark_order_ready(self, id: strawberry.ID) -> Order | None:
        return to_order(await call_service(services.mark_ready(int(id))))

    @strawberry.mutation
    async def mark_order_delivered(self, id: strawberry.ID) -> Order | None:
        return to_order(await call_service(services.mark_delivered(int(id))))

    @strawberry.mutation
    async def cancel_order(self, id: strawberry.ID, reason: str) -> Order | None:
        return to_order(await call_service(services.cancel(int(id), reason)))


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def order_status_changed(
        self, order_id: strawberry.ID
    ) -> AsyncGenerator[Order, None]:
        oid = int(order_id)
        queue = events.subscribe(oid)
        try:
            row = await db.get_order(oid)
            if row is None:
                raise GraphQLError(
                    f"Заказ {oid} не найден", extensions={"code": "NOT_FOUND"}
                )
            current = to_order(row)
            yield current
            status = row.status
            while status not in FINAL_STATES:
                event = await queue.get()
                status = event.status
                fresh = await db.get_order(oid)
                if fresh is None:
                    break
                result = to_order(fresh)
                result.status = status
                yield result
        finally:
            events.unsubscribe(oid, queue)


schema = strawberry.Schema(
    query=Query, mutation=Mutation, subscription=Subscription
)
