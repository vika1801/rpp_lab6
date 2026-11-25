from decimal import Decimal
from app import db, events


class NotFound(Exception):
    pass


class TransitionNotAllowed(Exception):
    pass


class OrderValidationError(Exception):
    pass


async def create_order(restaurant_id: int, customer_name: str,
                       delivery_address: str, items: list[dict]):
    if not customer_name.strip() or not delivery_address.strip():
        raise OrderValidationError("Имя клиента и адрес доставки обязательны")
    if not 1 <= len(items) <= 10:
        raise OrderValidationError("В заказе должно быть от 1 до 10 позиций")

    restaurant = await db.get_restaurant(restaurant_id)
    if restaurant is None:
        raise NotFound(f"Ресторан {restaurant_id} не найден")

    dish_ids = [item["dish_id"] for item in items]
    if len(set(dish_ids)) != len(dish_ids):
        raise OrderValidationError("Одно блюдо нельзя добавлять несколькими позициями")

    total = Decimal("0.00")
    saved_items = []
    for item in items:
        quantity = item["quantity"]
        if not 1 <= quantity <= 20:
            raise OrderValidationError("Количество блюда должно быть от 1 до 20")
        dish = await db.get_dish(item["dish_id"])
        if dish is None:
            raise NotFound(f"Блюдо {item['dish_id']} не найдено")
        if dish.restaurant_id != restaurant_id:
            raise OrderValidationError("Все блюда заказа должны принадлежать выбранному ресторану")
        price = Decimal(dish.price)
        total += price * quantity
        saved_items.append({"dish_id": dish.id, "quantity": quantity, "price": price})

    order = await db.add_order(
        restaurant_id, customer_name.strip(), delivery_address.strip(), total, saved_items
    )
    return order


async def _change(order_id: int, expected: str, target: str, event_name: str):
    order = await db.get_order(order_id)
    if order is None:
        raise NotFound(f"Заказ {order_id} не найден")
    if order.status != expected:
        raise TransitionNotAllowed(
            f"Событие {event_name} недопустимо в состоянии {order.status}"
        )
    updated = await db.update_order_status(order_id, target)
    events.publish(events.OrderStatusChanged(order_id, target))
    return updated


async def accept(order_id: int):
    return await _change(order_id, "CREATED", "ACCEPTED", "accept")


async def mark_ready(order_id: int):
    return await _change(order_id, "ACCEPTED", "READY", "mark_ready")


async def mark_delivered(order_id: int):
    return await _change(order_id, "READY", "DELIVERED", "mark_delivered")


async def cancel(order_id: int, reason: str):
    if not 3 <= len(reason.strip()) <= 200:
        raise OrderValidationError("Причина отмены должна содержать от 3 до 200 символов")
    order = await db.get_order(order_id)
    if order is None:
        raise NotFound(f"Заказ {order_id} не найден")
    if order.status not in ("CREATED", "ACCEPTED"):
        raise TransitionNotAllowed(
            f"Событие cancel недопустимо в состоянии {order.status}"
        )
    updated = await db.update_order_status(order_id, "CANCELLED", reason.strip())
    events.publish(events.OrderStatusChanged(order_id, "CANCELLED"))
    return updated
