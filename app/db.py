import os
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, select, text
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://lr6_user:lr6_password@localhost:5432/lr6_db",
)

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    __tablename__ = "restaurants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(250), nullable=False)


class Dish(Base):
    __tablename__ = "dishes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(250), nullable=False)
    cancel_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_restaurant(restaurant_id: int):
    async with SessionLocal() as session:
        return await session.get(Restaurant, restaurant_id)


async def get_dish(dish_id: int):
    async with SessionLocal() as session:
        return await session.get(Dish, dish_id)


async def get_order(order_id: int):
    async with SessionLocal() as session:
        return await session.get(Order, order_id)


async def get_items(order_id: int):
    async with SessionLocal() as session:
        result = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
        )
        return list(result.scalars().all())


async def list_restaurants():
    async with SessionLocal() as session:
        result = await session.execute(select(Restaurant).order_by(Restaurant.id))
        return list(result.scalars().all())


async def list_dishes(restaurant_id: int):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Dish).where(Dish.restaurant_id == restaurant_id).order_by(Dish.id)
        )
        return list(result.scalars().all())


async def get_restaurants(ids: list[int]) -> dict[int, Restaurant]:
    if not ids:
        return {}
    async with SessionLocal() as session:
        result = await session.execute(select(Restaurant).where(Restaurant.id.in_(set(ids))))
        return {row.id: row for row in result.scalars().all()}


async def get_dishes(ids: list[int]) -> dict[int, Dish]:
    if not ids:
        return {}
    async with SessionLocal() as session:
        result = await session.execute(select(Dish).where(Dish.id.in_(set(ids))))
        return {row.id: row for row in result.scalars().all()}


async def get_items_by_orders(order_ids: list[int]) -> dict[int, list[OrderItem]]:
    if not order_ids:
        return {}
    async with SessionLocal() as session:
        result = await session.execute(
            select(OrderItem).where(OrderItem.order_id.in_(set(order_ids))).order_by(OrderItem.id)
        )
        grouped = defaultdict(list)
        for item in result.scalars().all():
            grouped[item.order_id].append(item)
        return dict(grouped)


async def list_orders(status: str | None = None):
    async with SessionLocal() as session:
        query = select(Order).order_by(Order.created_at.desc())
        if status is not None:
            query = query.where(Order.status == status)
        result = await session.execute(query)
        return list(result.scalars().all())


async def add_order(restaurant_id: int, customer_name: str, delivery_address: str,
                    total: Decimal, items_data: list[dict]):
    async with SessionLocal() as session:
        order = Order(
            restaurant_id=restaurant_id, status="CREATED", total=total,
            created_at=datetime.now(timezone.utc), customer_name=customer_name,
            delivery_address=delivery_address, cancel_reason=None
        )
        session.add(order)
        await session.flush()
        for item in items_data:
            session.add(OrderItem(
                order_id=order.id, dish_id=item["dish_id"],
                quantity=item["quantity"], price=item["price"]
            ))
        await session.commit()
        await session.refresh(order)
        return order


async def update_order_status(order_id: int, status: str, cancel_reason: str | None = None):
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if order is None:
            return None
        order.status = status
        if cancel_reason is not None:
            order.cancel_reason = cancel_reason
        await session.commit()
        await session.refresh(order)
        return order


async def seed_is_empty() -> bool:
    async with SessionLocal() as session:
        result = await session.execute(select(Restaurant.id).limit(1))
        return result.first() is None


async def clear_and_seed_data(restaurants_data, dishes_data, orders_data):
    async with SessionLocal() as session:
        # Delete in dependency order; used only by the explicit seed command.
        await session.execute(text(
            "TRUNCATE TABLE order_items, orders, dishes, restaurants RESTART IDENTITY CASCADE"
        ))
        await session.commit()

        restaurant_objects = [Restaurant(**x) for x in restaurants_data]
        session.add_all(restaurant_objects)
        await session.flush()
        dish_objects = [Dish(**x) for x in dishes_data]
        session.add_all(dish_objects)
        await session.flush()
        order_objects = [Order(**x) for x in orders_data]
        session.add_all(order_objects)
        await session.flush()
        # Seed order items are passed separately through orders_data["_items"]? handled below.
        await session.commit()


async def insert_seed_items(items_data):
    async with SessionLocal() as session:
        session.add_all([OrderItem(**x) for x in items_data])
        await session.commit()
