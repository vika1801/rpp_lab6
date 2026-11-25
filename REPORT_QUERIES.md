# Запросы для раздела VII и отчёта

http://localhost:8000/graphql.

## 7.1.1 Заказ со всеми связанными данными
Сначала узнали существующий ID в запросе `orders`, затем подставили его вместо `1`.

```graphql
query {
  order(id: "1") {
    id
    status
    total
    createdAt
    customerName
    deliveryAddress
    restaurant {
      id
      name
      address
      dishes { id name price }
    }
    items {
      quantity
      price
      amount
      dish { id name price }
    }
  }
}
```

## 7.1.2 Заказы ACCEPTED
```graphql
query {
  orders(status: ACCEPTED) {
    id status total customerName
  }
}
```

## Запрос A для раздела IV
```graphql
query A($status: OrderStatus) {
  orders(status: $status) {
    id
    status
    total
    customerName
    restaurant { name }
    items {
      quantity
      price
      dish { name }
    }
  }
}
```
Variables для CANCELLED:
```json
{"status": "CANCELLED"}
```
Variables для READY:
```json
{"status": "READY"}
```
Variables без фильтра:
```json
{}
```
Для сравнения 4.1 и 4.2 переключайте режим в `docker-compose.yml`:
- без загрузчиков (задача 4.1): `USE_DATALOADER: "false"`;
- с загрузчиками (задача 4.2): `USE_DATALOADER: "true"`.
После изменения пересоберите и перезапустите API: `docker compose up --build -d api`. Перед каждым запросом можно очистить журнал командой `docker compose logs --since=1s api` либо отметить момент начала. Считайте строки SQL `SELECT` в журнале приложения. Значение `число заказов в ответе` получите по количеству объектов в ответе GraphQL.

## 7.2.1 Создание заказа
В текущем seed есть блюдо 1 ресторана 1. Выполните:
```graphql
mutation {
  createOrder(input: {
    restaurantId: "1"
    customerName: "Тестовый клиент"
    deliveryAddress: "ул. Примерная, дом 10"
    items: [{dishId: "1", quantity: 2}]
  }) {
    id status total createdAt
  }
}
```
Запомните возвращённый ID. Далее по очереди выполняйте, подставляя этот ID:
```graphql
mutation { acceptOrder(id: "101") { id status } }
```
```graphql
mutation { markOrderReady(id: "101") { id status } }
```
```graphql
mutation { markOrderDelivered(id: "101") { id status } }
```

## 7.2.2 Ошибка VALIDATION_ERROR
Блюдо 11 относится ко второму ресторану, поэтому нельзя использовать его с restaurantId "1":
```graphql
mutation {
  createOrder(input: {
    restaurantId: "1"
    customerName: "Проверка ошибки"
    deliveryAddress: "ул. Тестовая, дом 1"
    items: [{dishId: "11", quantity: 1}]
  }) { id status }
}
```

## 7.2.3 Ошибка TRANSITION_NOT_ALLOWED
В seed заказ 5 имеет состояние CANCELLED:
```graphql
mutation { acceptOrder(id: "5") { id status } }
```
Проверьте, что состояние не изменилось:
```graphql
query { order(id: "5") { id status } }
```

## 7.2.4 Ошибка NOT_FOUND
```graphql
mutation { acceptOrder(id: "999999") { id status } }
```

## 7.3 Подписка
Создайте новый заказ мутацией из пункта 7.2.1. Откройте GraphiQL во второй вкладке. В первой вкладке запустите подписку, заменив ID:
```graphql
subscription {
  orderStatusChanged(orderId: "101") {
    id
    status
    total
  }
}
```
Во второй вкладке последовательно выполните acceptOrder, markOrderReady и markOrderDelivered. В первой вкладке должны появиться состояния CREATED, ACCEPTED, READY, DELIVERED, после чего подписка завершится.
