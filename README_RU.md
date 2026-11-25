# Лабораторная работа № 6 — GraphQL-интерфейс

## Запуск (Windows / PowerShell)

1. Установить Docker Desktop и запустить его.
2. Открыть PowerShell в папке проекта.
3. Выполнить:
   ```powershell
   docker compose up --build -d
   ```
4. Заполнить базу:
   ```powershell
   docker compose run --rm api python -m app.seed
   ```
5. Открыть GraphiQL:
   http://localhost:8000/graphql

Просмотр журнала:
```powershell
docker compose logs -f api
```
Остановка:
```powershell
docker compose down
```
Полная очистка БД (удалит данные):
```powershell
docker compose down -v
```

## Примечание
Команда seed очищает таблицы и заново создаёт демонстрационные данные. Не запускайте её повторно, если хотите сохранить собственные тестовые заказы.
