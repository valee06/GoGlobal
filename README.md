# GoGlobal

Сервис сопровождения академического обмена. Три роли: студент-обменник,
study-buddy (интерфейс на английском, FR-45), куратор.

## Стек

- Python 3.12, Django 6.0 (версии зафиксированы в requirements.txt)
- PostgreSQL 17 (локально — Docker)
- Django templates + htmx

## Запуск локально

1. `python3.12 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Скопировать `.env.example` в `.env` и заполнить значения
4. Поднять БД:
   `docker run --name goglobal-pg -e POSTGRES_DB=goglobal -e POSTGRES_USER=goglobal -e POSTGRES_PASSWORD=&lt;пароль&gt; -p 5432:5432 -d postgres:17`
5. `python manage.py migrate`
6. `python manage.py runserver` → http://127.0.0.1:8000

## Модель пользователей

- Вход по email (FR-22), логина нет
- Роли: student / buddy / curator (FR-25)
- `is_approved = False` по умолчанию: доступ только после ручного
  служебного подтверждения (FR-27), автоматического доступа нет
- Профили ролей: StudentProfile, BuddyProfile, CuratorProfile
  (OneToOne к User); поля маршрутов и связей добавляются в блоке 2