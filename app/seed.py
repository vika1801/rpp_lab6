import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import db


RESTAURANT_NAMES = [
    ("Итальянская кухня", "ул. Ленина, 10"),
    ("Суши и роллы", "ул. Советская, 15"),
    ("Бургерная", "пр. Карла Маркса, 20"),
    ("Домашняя кухня", "ул. Кирова, 7"),
    ("Пиццерия", "ул. Мира, 25"),
]
DISH_NAMES = [
    ["Маргарита", "Пепперони", "Карбонара", "Лазанья", "Ризотто",
     "Цезарь", "Тирамису", "Брускетта", "Минестроне", "Паста Болоньезе"],
    ["Филадельфия", "Калифорния", "Дракон", "Нигири", "Мисо-суп",
     "Том-ям", "Эби маки", "Сашими", "Темпура", "Унаги ролл"],
    ["Чизбургер", "Бургер классический", "Картофель фри", "Наггетсы", "Хот-дог",
     "Крылышки", "Бургер BBQ", "Молочный коктейль", "Салат коул-слоу", "Луковые кольца"],
    ["Борщ", "Котлета с пюре", "Пельмени", "Гречка с грибами", "Сырники",
     "Оладьи", "Голубцы", "Суп куриный", "Плов", "Блины"],
    ["Четыре сыра", "Гавайская", "Мясная", "Деревенская", "Пицца с грибами",
     "Кальцоне", "Фокачча", "Пицца с ветчиной", "Пицца овощная", "Пицца BBQ"],
]
STATUSES = ["CREATED", "ACCEPTED", "READY", "DELIVERED", "CANCELLED"]


async def main():
    await db.create_tables()
    restaurants = [
        {"name": name, "address": address}
        for name, address in RESTAURANT_NAMES
    ]
    dishes = []
    for restaurant_id, names in enumerate(DISH_NAMES, start=1):
        for index, name in enumerate(names):
            dishes.append({
                "restaurant_id": restaurant_id,
                "name": name,
                "price": Decimal(150 + index * 35 + restaurant_id * 10).quantize(Decimal("0.01")),
            })

    # IDs are deterministic after clearing the seed tables in an empty lab database.
    orders = []
    item_rows = []
    for i in range(100):
        restaurant_id = (i % 5) + 1
        status = STATUSES[i % 5]
        dish_id = (restaurant_id - 1) * 10 + (i % 10) + 1
        quantity = (i % 3) + 1
        price = Decimal(150 + (dish_id - 1) % 10 * 35 + restaurant_id * 10).quantize(Decimal("0.01"))
        total = price * quantity
        orders.append({
            "restaurant_id": restaurant_id,
            "status": status,
            "total": total,
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=i),
            "customer_name": f"Клиент {i + 1}",
            "delivery_address": f"ул. Тестовая, дом {i + 1}",
            "cancel_reason": "Клиент отменил заказ" if status == "CANCELLED" else None,
        })

    # Seed parent records first, then create one order item for every order.
    await db.clear_and_seed_data(restaurants, dishes, orders)
    for order_id in range(1, 101):
        restaurant_id = ((order_id - 1) % 5) + 1
        dish_id = (restaurant_id - 1) * 10 + ((order_id - 1) % 10) + 1
        quantity = ((order_id - 1) % 3) + 1
        price = Decimal(150 + (dish_id - 1) % 10 * 35 + restaurant_id * 10).quantize(Decimal("0.01"))
        item_rows.append({
            "order_id": order_id, "dish_id": dish_id,
            "quantity": quantity, "price": price
        })
    await db.insert_seed_items(item_rows)
    print("База заполнена: 5 ресторанов, 50 блюд, 100 заказов.")


if __name__ == "__main__":
    asyncio.run(main())
