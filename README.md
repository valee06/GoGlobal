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

3. Собрать образы и запустить приложение с базой данных:

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

Проверить конфигурацию Django:

```bash
docker compose exec web python manage.py check
```

## Ручной запуск проверок CI

Если GitHub Actions недоступен или необходимо локально проверить изменения, можно выполнить основные проверки вручную.

1. Убедиться, что база данных запущена:

```bash
docker compose up -d db
```

2. Проверить конфигурацию Django:

```bash
docker compose run --rm web python manage.py check
```

3. Проверить согласованность миграций:

```bash
docker compose run --rm web python manage.py makemigrations --check --dry-run
```

4. Запустить тесты:

```bash
docker compose run --rm web python manage.py test
```

Команды выполняются в контейнере приложения и используют зависимости, установленные при сборке Docker-образа.

При необходимости пересобрать образ после изменения зависимостей:

```bash
docker compose build web
```

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
