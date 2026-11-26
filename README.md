# GoGlobal

Сервис сопровождения академического обмена. В системе есть три роли: студент-обменник, study-buddy и куратор.

## Технологии

- Python 3.12
- Django 6.0
- PostgreSQL 17
- Django templates и htmx
- Docker Compose для локального запуска

## Роли пользователей

- Вход выполняется по электронной почте.
- Поддерживаются роли `student`, `buddy` и `curator`.
- Для buddy и куратора доступ открывается после ручного одобрения.
- У каждой роли есть свой профиль.

## Локальный запуск через Docker Compose

Для запуска понадобятся Git и Docker Desktop.

1. Склонируйте репозиторий и перейдите в папку проекта.
2. Создайте локальный файл настроек:

   ```bash
   cp .env.example .env
   ```

3. Откройте `.env` и задайте `DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD`. Не отправляйте этот файл в Git и не публикуйте секреты.
4. Соберите образы и запустите приложение с базой данных:

   ```bash
   docker compose up --build -d
   ```

5. Примените миграции:

   ```bash
   docker compose exec web python manage.py migrate
   ```

6. При необходимости создайте администратора:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

7. Откройте приложение в браузере: <http://localhost:8000>

## Проверка приложения

Посмотреть состояние контейнеров:

```bash
docker compose ps
```

Проверить конфигурацию Django:

```bash
docker compose exec web python manage.py check
```

Проверить, что миграции соответствуют моделям:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
```

Запустить тесты:

```bash
docker compose exec web python manage.py test
```

## Ручной запуск проверок CI

Если GitHub Actions недоступен, основные проверки можно выполнить вручную:

1. Запустите базу данных:

   ```bash
   docker compose up -d db
   ```

2. Проверьте конфигурацию Django:

   ```bash
   docker compose run --rm web python manage.py check
   ```

3. Проверьте миграции:

   ```bash
   docker compose run --rm web python manage.py makemigrations --check --dry-run
   ```

4. Запустите тесты:

   ```bash
   docker compose run --rm web python manage.py test
   ```

После изменения зависимостей пересоберите образ приложения:

```bash
docker compose build web
```

## Журнал событий

Технические сообщения приложения содержат идентификатор события. Секреты в сообщениях маскируются. Не добавляйте в журнал пароли, коды подтверждения и другие личные данные.

Команда ниже только показывает, сколько старых записей журнала можно удалить:

```bash
docker compose exec web python manage.py cleanup_audit_events
```

Чтобы выполнить удаление, добавьте флаг `--apply`:

```bash
docker compose exec web python manage.py cleanup_audit_events --apply
```

## Полезные команды Docker Compose

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

## Локальный запуск Django без Docker

Для запуска вне Docker требуется Python 3.12 и доступная PostgreSQL.

1. Создайте и активируйте виртуальное окружение:

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

2. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

3. Создайте `.env` из примера и заполните нужные настройки:

   ```bash
   cp .env.example .env
   ```

4. Примените миграции и запустите сервер:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

5. Откройте <http://127.0.0.1:8000>.
