
# GoGlobal

## Требования

Для локального запуска необходимы:
- Docker Desktop
- Git

Для локального запуска Django вне Docker требуется Python 3.12.x.

## Первоначальная настройка

1. Склонировать репозиторий и перейти в папку проекта.

2. Создать файл с локальными настройками:

```bash
cp .env.example .env
```

3. Запустить приложение и базу данных:

```bash
docker compose up --build -d
```

4. Выполнить миграции базы данных:

```bash
docker compose exec web python manage.py migrate
```

5. Открыть приложение в браузере:

http://localhost:8000

## Проверка состояния

Проверить состояние контейнеров:

```bash
docker compose ps
```

Контейнер базы данных должен иметь статус `healthy`, а контейнер приложения — `Up`.

## Полезные команды

Запустить контейнеры:

```bash
docker compose up -d
```

Остановить контейнеры:

```bash
docker compose down
```

Посмотреть логи приложения:

```bash
docker compose logs -f web
```

Посмотреть логи базы данных:

```bash
docker compose logs -f db
```

Перезапустить приложение:

```bash
docker compose restart web
```
