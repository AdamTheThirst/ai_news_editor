# API_CONTRACTS.md

## 1. Назначение документа

Этот документ описывает внутренние API-контракты приложения **«Редактор статей»**.

Приложение разрабатывается как единый Python-проект на **FastAPI + SQLite + Jinja2/HTMX/Alpine.js/vanilla JS**. Несмотря на то, что UI рендерится сервером, часть действий должна выполняться через JSON endpoints: создание генерации, polling статуса, загрузка `.docx`, скачивание `.txt`, админские действия.

Документ предназначен для Codex и должен использоваться вместе с:

- `README.md`
- `PROJECT_BRIEF.md`
- `PRODUCT_REQUIREMENTS.md`
- `USER_FLOWS.md`
- `ARCHITECTURE.md`
- `DATABASE_SCHEMA.md`
- `PROMPTING_SPEC.md`
- `MODEL_ADAPTER.md`
- `ADMIN_PANEL.md`
- `SECURITY.md`

## 2. Общие принципы API

### 2.1. Тип приложения

Приложение является серверным веб-приложением. Основной интерфейс работает через HTML-страницы, но для интерактивных действий используются JSON endpoints.

Допустимая схема:

- обычные страницы: `GET`, возвращают HTML;
- формы: `POST`, могут возвращать redirect или HTML-фрагмент;
- интерактивные операции: `POST/GET`, возвращают JSON;
- polling генерации: `GET`, возвращает JSON;
- скачивание файла: `GET`, возвращает `text/plain` attachment.

### 2.2. Базовый URL

Локально при разработке:

```txt
http://127.0.0.1:8000
```

На VPS URL задаётся через nginx/reverse proxy.

### 2.3. Формат данных

Для JSON endpoints:

```http
Content-Type: application/json
Accept: application/json
```

Для загрузки `.docx`:

```http
Content-Type: multipart/form-data
```

### 2.4. Авторизация

Авторизация пользователей выполняется через cookie-based session.

API не должен требовать JWT в первой версии.

После успешного входа backend устанавливает защищённую session cookie. Все приватные endpoints проверяют текущего пользователя через session.

### 2.5. Роли

Поддерживаются две роли:

```txt
user
admin
```

Роль `user`:

- видит только свои диалоги;
- создаёт диалоги;
- генерирует статьи;
- дорабатывает статьи;
- скачивает свои статьи в `.txt`;
- видит историю своих чатов.

Роль `admin`:

- имеет все права `user`;
- видит все диалоги всех пользователей;
- видит пользователей;
- создаёт пользователей;
- блокирует/разблокирует пользователей;
- меняет пароль пользователю;
- редактирует мастер-промт;
- редактирует системные лимиты;
- видит debug prompt;
- видит технические логи генераций.

### 2.6. Единый формат ошибки

Все JSON endpoints должны возвращать ошибки в едином формате:

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "Короткое понятное сообщение для пользователя.",
    "details": {}
  }
}
```

Поле `details` опционально, но должно присутствовать как объект.

Примеры кодов ошибок:

```txt
unauthorized
forbidden
not_found
validation_error
input_too_long
unsupported_file_type
file_parse_error
active_generation_exists
generation_not_found
generation_timeout
model_error
model_bad_response
server_error
```

### 2.7. Единый формат успешного JSON-ответа

```json
{
  "ok": true,
  "data": {}
}
```

Для простых операций `data` может содержать только нужные поля.

### 2.8. Даты и время

Все даты в API возвращаются в ISO 8601 UTC:

```txt
2026-06-16T12:30:00Z
```

В UI даты можно отображать в локальном часовом поясе пользователя или сервера.

## 3. HTML pages

## 3.1. `GET /`

Главная страница.

Поведение:

- если пользователь не авторизован — redirect на `/login`;
- если пользователь авторизован — redirect на `/chats` или открытие последнего диалога.

Ответ:

```http
302 Found
Location: /login
```

или

```http
302 Found
Location: /chats
```

## 3.2. `GET /login`

Страница входа.

Доступ:

- публичный endpoint.

Возвращает HTML-форму:

- `username`;
- `password`;
- кнопка «Войти».

## 3.3. `POST /login`

Отправка формы входа.

Content-Type:

```http
application/x-www-form-urlencoded
```

Поля:

```txt
username=ivan
password=secret
```

Успешное поведение:

- устанавливает session cookie;
- обновляет `last_login_at` у пользователя;
- redirect на `/chats`.

Ошибки:

- неверный логин/пароль;
- пользователь заблокирован.

## 3.4. `POST /logout`

Выход пользователя.

Поведение:

- удаляет session;
- redirect на `/login`.

## 3.5. `GET /chats`

Страница списка диалогов и основного интерфейса.

Доступ:

- `user`, `admin`.

Для `user` показывает только его диалоги.

Для `admin` в обычном пользовательском режиме также может показывать его собственные диалоги. Просмотр всех диалогов админом находится в `/admin/chats`.

## 3.6. `GET /chats/{chat_id}`

Страница конкретного диалога.

Доступ:

- владелец диалога;
- `admin`.

На странице должны быть:

- название диалога;
- история сообщений;
- последняя версия статьи;
- подсказка: «ИИ помнит только последнюю версию статьи»;
- опции генерации над полем ввода;
- поле ввода сырого материала или инструкции на доработку;
- загрузка `.docx`;
- кнопка отправки;
- кнопка копирования последней статьи;
- кнопка скачивания `.txt`;
- индикатор статуса генерации.

## 4. Auth API

## 4.1. `GET /api/me`

Возвращает текущего пользователя.

Доступ:

- авторизованный пользователь.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "is_active": true,
    "created_at": "2026-06-16T12:30:00Z",
    "last_login_at": "2026-06-16T13:00:00Z"
  }
}
```

Ошибки:

- `401 unauthorized`.

## 5. Chats API

## 5.1. `GET /api/chats`

Возвращает список диалогов текущего пользователя.

Доступ:

- `user`, `admin`.

Query parameters:

```txt
limit=30
offset=0
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 10,
        "title": "Запуск нового продукта",
        "owner_user_id": 2,
        "owner_username": "pr_manager",
        "created_at": "2026-06-16T12:30:00Z",
        "updated_at": "2026-06-16T12:45:00Z",
        "last_message_preview": "Подготовь новость о запуске...",
        "last_article_version_id": 7
      }
    ],
    "limit": 30,
    "offset": 0,
    "total": 1
  }
}
```

Для обычного пользователя поле `owner_username` можно возвращать, но оно не обязательно для UI.

## 5.2. `POST /api/chats`

Создаёт новый диалог.

Доступ:

- `user`, `admin`.

Запрос:

```json
{
  "title": "Название диалога"
}
```

Валидация:

- `title` обязателен;
- `title` не должен быть пустым;
- рекомендуемый лимит: 3–120 символов.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 10,
    "title": "Название диалога",
    "created_at": "2026-06-16T12:30:00Z"
  }
}
```

## 5.3. `GET /api/chats/{chat_id}`

Возвращает данные диалога.

Доступ:

- владелец;
- `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 10,
    "title": "Запуск нового продукта",
    "owner_user_id": 2,
    "owner_username": "pr_manager",
    "created_at": "2026-06-16T12:30:00Z",
    "updated_at": "2026-06-16T12:45:00Z",
    "last_article_version_id": 7
  }
}
```

## 6. Messages API

## 6.1. `GET /api/chats/{chat_id}/messages`

Возвращает сообщения диалога.

Доступ:

- владелец;
- `admin`.

Query parameters:

```txt
limit=100
offset=0
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 101,
        "chat_id": 10,
        "role": "user",
        "content": "Сырой материал статьи...",
        "created_at": "2026-06-16T12:31:00Z",
        "metadata": {
          "tone": "neutral_news",
          "length_preset": "1200_1500",
          "composition": "inverted_pyramid",
          "paragraphs_count": 4
        }
      },
      {
        "id": 102,
        "chat_id": 10,
        "role": "assistant",
        "content": "# Варианты заголовков\n...",
        "created_at": "2026-06-16T12:32:30Z",
        "metadata": {
          "article_version_id": 7,
          "generation_job_id": 55
        }
      }
    ],
    "limit": 100,
    "offset": 0,
    "total": 2
  }
}
```

Роли сообщений:

```txt
user
assistant
system
```

`system` не должен показываться обычному пользователю, если содержит технический prompt.

## 7. Article generation API

## 7.1. Основной сценарий генерации

Генерация статьи запускается асинхронно с точки зрения UI.

Последовательность:

1. UI отправляет запрос `POST /api/chats/{chat_id}/generate`.
2. Backend валидирует входные данные.
3. Backend создаёт запись в `generation_jobs` со статусом `queued`.
4. Backend возвращает `job_id`.
5. Background worker берёт job в работу.
6. UI показывает статус «ИИ думает…» и опрашивает `GET /api/generation-jobs/{job_id}`.
7. После завершения backend сохраняет:
   - сообщение пользователя;
   - сообщение ассистента;
   - новую версию статьи;
   - технический лог генерации.
8. UI получает `status=completed` и обновляет чат.

## 7.2. `POST /api/chats/{chat_id}/generate`

Создаёт задачу генерации новой статьи или доработки последней статьи.

Доступ:

- владелец диалога;
- `admin`.

Запрос:

```json
{
  "mode": "new_article",
  "raw_material": "Сырой материал или набор фактов...",
  "context": "Опциональный контекст публикации...",
  "tone": "neutral_news",
  "length_preset": "1200_1500",
  "custom_target_chars": null,
  "composition": "inverted_pyramid",
  "paragraphs_count": 4,
  "generate_headlines_count": 3
}
```

Для доработки статьи:

```json
{
  "mode": "revise_article",
  "revision_instruction": "Сделай текст короче и более деловым.",
  "tone": "business",
  "length_preset": "1200_1500",
  "custom_target_chars": null,
  "composition": "inverted_pyramid",
  "paragraphs_count": 4,
  "generate_headlines_count": 3
}
```

Поле `mode`:

```txt
new_article
revise_article
```

### 7.2.1. Поля для `new_article`

| Поле | Тип | Обязательное | Описание |
|---|---:|---:|---|
| `mode` | string | да | `new_article` |
| `raw_material` | string | да | Сырой материал, факты, цитаты, описание инфоповода |
| `context` | string/null | нет | Дополнительный контекст публикации |
| `tone` | string | да | Тон текста |
| `length_preset` | string | да | Пресет длины |
| `custom_target_chars` | int/null | нет | Если UI позже разрешит ручной ввод длины |
| `composition` | string | да | Композиция статьи |
| `paragraphs_count` | int | да | Желаемое количество абзацев |
| `generate_headlines_count` | int | да | Количество вариантов заголовков |

### 7.2.2. Поля для `revise_article`

| Поле | Тип | Обязательное | Описание |
|---|---:|---:|---|
| `mode` | string | да | `revise_article` |
| `revision_instruction` | string | да | Инструкция пользователя по доработке |
| `tone` | string | да | Тон текста |
| `length_preset` | string | да | Пресет длины |
| `custom_target_chars` | int/null | нет | Если UI позже разрешит ручной ввод длины |
| `composition` | string | да | Композиция статьи |
| `paragraphs_count` | int | да | Желаемое количество абзацев |
| `generate_headlines_count` | int | да | Количество вариантов заголовков |

При `revise_article` backend обязан передать модели последнюю версию статьи.

Если последней версии нет, нужно вернуть ошибку:

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "В этом диалоге ещё нет статьи для доработки.",
    "details": {}
  }
}
```

### 7.2.3. Допустимые значения `tone`

```txt
neutral_news
business
light_magazine
human_interest
```

Человекочитаемые названия:

| Код | Название в UI |
|---|---|
| `neutral_news` | Нейтрально-новостной |
| `business` | Деловой |
| `light_magazine` | Лёгкий журнальный |
| `human_interest` | Human interest |

### 7.2.4. Допустимые значения `length_preset`

```txt
800_1500
1501_2500
2501_4000
1200_1500
```

Рекомендация для MVP:

- в UI показывать пресеты `800–1500`, `1501–2500`, `2501–4000`;
- дефолтный пресет — `1200–1500` или отдельное значение `1200_1500`;
- если выбран дефолт, целевой диапазон: 1200–1500 символов.

Важно: если исходных фактов хватает только на меньший объём, модель не должна растягивать текст выдуманными подробностями.

### 7.2.5. Допустимые значения `composition`

```txt
inverted_pyramid
chronological
fact_context_consequences
problem_reaction_consequences
human_interest
explainer
aida_no_cta
```

Человекочитаемые названия:

| Код | Название в UI | Описание |
|---|---|---|
| `inverted_pyramid` | Перевёрнутая пирамида | Главное в начале, затем детали и контекст |
| `chronological` | Хронологическая | События по порядку |
| `fact_context_consequences` | Факт → контекст → последствия | Сначала факт, затем объяснение и значение |
| `problem_reaction_consequences` | Проблема → реакция → последствия | Для конфликтов, кризисов, изменений |
| `human_interest` | Human interest | Через человека, ситуацию или эмоциональный фокус без выдумывания деталей |
| `explainer` | Explainer | Простое объяснение события и его значения |
| `aida_no_cta` | AIDA без CTA | Внимание → интерес → детали → значимость, без призыва к действию |

### 7.2.6. Валидация генерации

Backend обязан проверить:

- пользователь авторизован;
- пользователь имеет доступ к диалогу;
- пользователь активен;
- `raw_material` не пустой для `new_article`;
- `revision_instruction` не пустой для `revise_article`;
- длина `raw_material` не превышает `max_input_chars` из системных настроек;
- `tone` входит в список допустимых;
- `length_preset` входит в список допустимых;
- `composition` входит в список допустимых;
- `paragraphs_count` в допустимом диапазоне, например 1–12;
- у пользователя нет активной генерации в этом диалоге или глобально, если включено такое ограничение.

Ошибка при превышении лимита:

```json
{
  "ok": false,
  "error": {
    "code": "input_too_long",
    "message": "Материал слишком длинный. Максимум: 5000 символов.",
    "details": {
      "max_input_chars": 5000,
      "actual_chars": 7340
    }
  }
}
```

Ошибка при активной генерации:

```json
{
  "ok": false,
  "error": {
    "code": "active_generation_exists",
    "message": "В этом диалоге уже выполняется генерация. Дождитесь завершения.",
    "details": {
      "job_id": 55
    }
  }
}
```

Успешный ответ:

```json
{
  "ok": true,
  "data": {
    "job_id": 55,
    "status": "queued",
    "message": "Задача поставлена в очередь."
  }
}
```

## 7.3. `GET /api/generation-jobs/{job_id}`

Возвращает статус генерации.

Доступ:

- владелец связанного диалога;
- `admin`.

Ответ для очереди:

```json
{
  "ok": true,
  "data": {
    "id": 55,
    "chat_id": 10,
    "status": "queued",
    "position": 1,
    "message": "Задача ожидает обработки.",
    "created_at": "2026-06-16T12:31:00Z",
    "started_at": null,
    "completed_at": null,
    "failed_at": null
  }
}
```

Ответ для выполнения:

```json
{
  "ok": true,
  "data": {
    "id": 55,
    "chat_id": 10,
    "status": "running",
    "position": null,
    "message": "ИИ думает над материалом...",
    "created_at": "2026-06-16T12:31:00Z",
    "started_at": "2026-06-16T12:31:05Z",
    "completed_at": null,
    "failed_at": null
  }
}
```

Ответ для завершения:

```json
{
  "ok": true,
  "data": {
    "id": 55,
    "chat_id": 10,
    "status": "completed",
    "message": "Готово.",
    "assistant_message_id": 102,
    "article_version_id": 7,
    "created_at": "2026-06-16T12:31:00Z",
    "started_at": "2026-06-16T12:31:05Z",
    "completed_at": "2026-06-16T12:32:30Z",
    "failed_at": null
  }
}
```

Ответ для ошибки:

```json
{
  "ok": true,
  "data": {
    "id": 55,
    "chat_id": 10,
    "status": "failed",
    "message": "Модель не ответила. Попробуйте повторить запрос.",
    "error_code": "generation_timeout",
    "created_at": "2026-06-16T12:31:00Z",
    "started_at": "2026-06-16T12:31:05Z",
    "completed_at": null,
    "failed_at": "2026-06-16T12:34:05Z"
  }
}
```

Допустимые статусы:

```txt
queued
running
completed
failed
cancelled
```

## 7.4. `POST /api/generation-jobs/{job_id}/retry`

Повторяет неудачную генерацию.

Доступ:

- владелец связанного диалога;
- `admin`.

Условия:

- исходный job имеет статус `failed`;
- исходные параметры сохранены в `generation_jobs.request_payload`;
- backend создаёт новый job, а не перезаписывает старый.

Ответ:

```json
{
  "ok": true,
  "data": {
    "job_id": 56,
    "status": "queued",
    "message": "Задача повторно поставлена в очередь."
  }
}
```

## 8. Article versions API

## 8.1. `GET /api/chats/{chat_id}/article-versions`

Возвращает версии статьи в диалоге.

Доступ:

- владелец;
- `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 7,
        "chat_id": 10,
        "version_number": 2,
        "created_from_message_id": 102,
        "created_at": "2026-06-16T12:32:30Z",
        "is_current": true,
        "preview": "Заголовок: Компания представила..."
      },
      {
        "id": 6,
        "chat_id": 10,
        "version_number": 1,
        "created_from_message_id": 99,
        "created_at": "2026-06-16T12:20:00Z",
        "is_current": false,
        "preview": "Заголовок: Новый сервис..."
      }
    ]
  }
}
```

## 8.2. `GET /api/article-versions/{version_id}`

Возвращает конкретную версию статьи.

Доступ:

- владелец связанного диалога;
- `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 7,
    "chat_id": 10,
    "version_number": 2,
    "title_options": [
      "Компания представила новый сервис",
      "Новый сервис выходит на рынок",
      "Бизнес запускает решение для клиентов"
    ],
    "lead": "Компания объявила о запуске нового сервиса...",
    "body": "Основной текст статьи...",
    "questions": [
      "Уточните дату запуска, если её нужно указать в статье."
    ],
    "full_text": "# Варианты заголовков\n...",
    "created_at": "2026-06-16T12:32:30Z",
    "is_current": true
  }
}
```

## 8.3. `POST /api/article-versions/{version_id}/restore`

Откат к предыдущей версии статьи.

Доступ:

- владелец связанного диалога;
- `admin`.

Поведение:

- указанная версия становится текущей;
- в чат добавляется системное или assistant-сообщение о восстановлении версии;
- новая генерация не запускается.

Ответ:

```json
{
  "ok": true,
  "data": {
    "restored_version_id": 6,
    "chat_id": 10,
    "message": "Версия статьи восстановлена."
  }
}
```

## 9. File upload API

## 9.1. `POST /api/uploads/docx/extract`

Загружает `.docx`, извлекает текст и возвращает его UI.

Важно: файл `.docx` после обработки должен быть удалён. На сервере сохраняется только извлечённый текст, если пользователь затем отправит его на генерацию.

Доступ:

- `user`, `admin`.

Content-Type:

```http
multipart/form-data
```

Поля:

```txt
file=<uploaded .docx>
```

Валидация:

- расширение `.docx`;
- MIME type по возможности проверяется;
- размер файла ограничивается настройкой или разумным дефолтом;
- извлечённый текст не должен превышать `max_input_chars`.

Успешный ответ:

```json
{
  "ok": true,
  "data": {
    "filename": "material.docx",
    "text": "Извлечённый текст...",
    "chars_count": 2310,
    "max_input_chars": 5000
  }
}
```

Ошибка неподдерживаемого формата:

```json
{
  "ok": false,
  "error": {
    "code": "unsupported_file_type",
    "message": "Можно загружать только файлы .docx.",
    "details": {}
  }
}
```

Ошибка парсинга:

```json
{
  "ok": false,
  "error": {
    "code": "file_parse_error",
    "message": "Не удалось извлечь текст из файла .docx.",
    "details": {}
  }
}
```

## 10. Download API

## 10.1. `GET /api/article-versions/{version_id}/download.txt`

Скачивает версию статьи в формате `.txt`.

Доступ:

- владелец связанного диалога;
- `admin`.

Ответ:

```http
200 OK
Content-Type: text/plain; charset=utf-8
Content-Disposition: attachment; filename="article-10-v2.txt"
```

Содержимое файла:

```txt
ВАРИАНТЫ ЗАГОЛОВКОВ
1. ...
2. ...
3. ...

ЛИД
...

СТАТЬЯ
...

ВОПРОСЫ / УТОЧНЕНИЯ
...
```

Если вопросов нет, раздел можно не добавлять или написать:

```txt
ВОПРОСЫ / УТОЧНЕНИЯ
Нет.
```

## 11. Options API

## 11.1. `GET /api/options/generation`

Возвращает справочники для UI: тоны, длины, композиции, дефолтные значения и лимиты.

Доступ:

- `user`, `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "defaults": {
      "tone": "neutral_news",
      "length_preset": "1200_1500",
      "composition": "inverted_pyramid",
      "paragraphs_count": 4,
      "generate_headlines_count": 3
    },
    "limits": {
      "max_input_chars": 5000,
      "min_paragraphs_count": 1,
      "max_paragraphs_count": 12
    },
    "tones": [
      {
        "code": "neutral_news",
        "label": "Нейтрально-новостной",
        "description": "Сдержанный информационный стиль без оценочных формулировок."
      },
      {
        "code": "business",
        "label": "Деловой",
        "description": "Более официальный стиль для корпоративных и деловых новостей."
      },
      {
        "code": "light_magazine",
        "label": "Лёгкий журнальный",
        "description": "Более живой стиль, но без потери фактической строгости."
      },
      {
        "code": "human_interest",
        "label": "Human interest",
        "description": "Фокус на человеке или ситуации, если такие данные есть в исходном материале."
      }
    ],
    "length_presets": [
      {
        "code": "1200_1500",
        "label": "1200–1500 символов",
        "min_chars": 1200,
        "max_chars": 1500,
        "is_default": true
      },
      {
        "code": "800_1500",
        "label": "800–1500 символов",
        "min_chars": 800,
        "max_chars": 1500,
        "is_default": false
      },
      {
        "code": "1501_2500",
        "label": "1501–2500 символов",
        "min_chars": 1501,
        "max_chars": 2500,
        "is_default": false
      },
      {
        "code": "2501_4000",
        "label": "2501–4000 символов",
        "min_chars": 2501,
        "max_chars": 4000,
        "is_default": false
      }
    ],
    "compositions": [
      {
        "code": "inverted_pyramid",
        "label": "Перевёрнутая пирамида",
        "description": "Главное в начале, затем детали и контекст."
      },
      {
        "code": "chronological",
        "label": "Хронологическая",
        "description": "События по порядку."
      },
      {
        "code": "fact_context_consequences",
        "label": "Факт → контекст → последствия",
        "description": "Сначала факт, затем объяснение и значение."
      },
      {
        "code": "problem_reaction_consequences",
        "label": "Проблема → реакция → последствия",
        "description": "Для конфликтов, кризисов и изменений."
      },
      {
        "code": "human_interest",
        "label": "Human interest",
        "description": "Через человека или ситуацию, только если это есть в исходных данных."
      },
      {
        "code": "explainer",
        "label": "Explainer",
        "description": "Простое объяснение события и его значения."
      },
      {
        "code": "aida_no_cta",
        "label": "AIDA без CTA",
        "description": "Внимание → интерес → детали → значимость, без призыва к действию."
      }
    ]
  }
}
```

## 12. Admin API

Все endpoints этого раздела доступны только роли `admin`.

## 12.1. `GET /admin`

HTML-страница админки.

Разделы:

- пользователи;
- все диалоги;
- настройки генерации;
- мастер-промт;
- технические логи;
- debug prompt.

## 12.2. `GET /api/admin/users`

Список пользователей.

Query parameters:

```txt
limit=50
offset=0
q=optional_search
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "is_active": true,
        "created_at": "2026-06-16T12:00:00Z",
        "last_login_at": "2026-06-16T13:00:00Z",
        "chats_count": 3
      },
      {
        "id": 2,
        "username": "pr_manager",
        "role": "user",
        "is_active": true,
        "created_at": "2026-06-16T12:10:00Z",
        "last_login_at": null,
        "chats_count": 0
      }
    ],
    "limit": 50,
    "offset": 0,
    "total": 2
  }
}
```

## 12.3. `POST /api/admin/users`

Создаёт пользователя.

Регистрация самостоятельная запрещена. Пользователей создаёт только админ.

Запрос:

```json
{
  "username": "pr_manager",
  "password": "temporary-password",
  "role": "user",
  "is_active": true
}
```

Валидация:

- `username` уникален;
- `username` не пустой;
- `password` соответствует минимальным требованиям;
- `role` только `user` или `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 2,
    "username": "pr_manager",
    "role": "user",
    "is_active": true,
    "created_at": "2026-06-16T12:10:00Z"
  }
}
```

## 12.4. `PATCH /api/admin/users/{user_id}`

Обновляет пользователя.

Запрос:

```json
{
  "role": "user",
  "is_active": false
}
```

Все поля опциональны.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 2,
    "username": "pr_manager",
    "role": "user",
    "is_active": false,
    "updated_at": "2026-06-16T13:00:00Z"
  }
}
```

Важно: нельзя случайно заблокировать последнего активного администратора. Backend должен проверять это ограничение.

## 12.5. `POST /api/admin/users/{user_id}/change-password`

Меняет пароль пользователя.

Запрос:

```json
{
  "new_password": "new-temporary-password"
}
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "message": "Пароль изменён."
  }
}
```

## 12.6. `GET /api/admin/chats`

Список всех диалогов всех пользователей.

Query parameters:

```txt
limit=50
offset=0
user_id=optional
q=optional_search
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 10,
        "title": "Запуск нового продукта",
        "owner_user_id": 2,
        "owner_username": "pr_manager",
        "created_at": "2026-06-16T12:30:00Z",
        "updated_at": "2026-06-16T12:45:00Z",
        "messages_count": 4,
        "article_versions_count": 2
      }
    ],
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

## 12.7. `GET /api/admin/settings`

Возвращает системные настройки.

Ответ:

```json
{
  "ok": true,
  "data": {
    "max_input_chars": 5000,
    "default_length_preset": "1200_1500",
    "default_tone": "neutral_news",
    "default_composition": "inverted_pyramid",
    "default_paragraphs_count": 4,
    "default_headlines_count": 3,
    "generation_timeout_seconds": 180,
    "max_concurrent_generations": 2,
    "model_base_url": "https://ai.example.com/v1",
    "model_name": "Qwen/Qwen3-32B",
    "debug_prompt_enabled": true
  }
}
```

Не возвращать `model_api_key` в API-ответе.

## 12.8. `PATCH /api/admin/settings`

Обновляет системные настройки.

Запрос:

```json
{
  "max_input_chars": 5000,
  "default_length_preset": "1200_1500",
  "default_tone": "neutral_news",
  "default_composition": "inverted_pyramid",
  "default_paragraphs_count": 4,
  "default_headlines_count": 3,
  "generation_timeout_seconds": 180,
  "max_concurrent_generations": 2,
  "model_base_url": "https://ai.example.com/v1",
  "model_name": "Qwen/Qwen3-32B",
  "debug_prompt_enabled": true
}
```

Все поля опциональны.

Ответ:

```json
{
  "ok": true,
  "data": {
    "message": "Настройки сохранены."
  }
}
```

`model_api_key` рекомендуется задавать через `.env`, а не через админку. Если позже потребуется менять ключ через UI, нужно хранить его отдельно и не возвращать в API.

## 12.9. `GET /api/admin/prompts/master`

Возвращает текущий основной мастер-промт.

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "name": "default_master_prompt",
    "content": "Ты — редактор новостных статей...",
    "version": 3,
    "updated_at": "2026-06-16T13:00:00Z"
  }
}
```

## 12.10. `PUT /api/admin/prompts/master`

Обновляет мастер-промт.

Запрос:

```json
{
  "content": "Ты — редактор новостных статей..."
}
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "name": "default_master_prompt",
    "version": 4,
    "updated_at": "2026-06-16T13:10:00Z",
    "message": "Мастер-промт сохранён."
  }
}
```

Требование:

- при обновлении промпта желательно сохранять предыдущую версию в истории промптов;
- если история промптов не реализована в MVP, хотя бы увеличить `version`.

## 12.11. `POST /api/admin/prompts/preview`

Собирает полный prompt для отладки, но не отправляет его в модель.

Доступ:

- только `admin`.

Запрос:

```json
{
  "mode": "new_article",
  "raw_material": "Компания сообщила о запуске сервиса...",
  "context": "Для публикации на корпоративном сайте.",
  "tone": "neutral_news",
  "length_preset": "1200_1500",
  "composition": "inverted_pyramid",
  "paragraphs_count": 4,
  "generate_headlines_count": 3
}
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "system_prompt": "Ты — редактор новостных статей...",
    "user_prompt": "Исходный материал:\n...",
    "messages": [
      {
        "role": "system",
        "content": "Ты — редактор новостных статей..."
      },
      {
        "role": "user",
        "content": "Исходный материал:\n..."
      }
    ],
    "estimated_input_chars": 3200
  }
}
```

## 12.12. `GET /api/admin/generation-logs`

Возвращает технические логи генераций.

Query parameters:

```txt
limit=50
offset=0
user_id=optional
chat_id=optional
status=optional
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 501,
        "job_id": 55,
        "user_id": 2,
        "username": "pr_manager",
        "chat_id": 10,
        "status": "completed",
        "input_chars": 2310,
        "requested_length_preset": "1200_1500",
        "model_name": "Qwen/Qwen3-32B",
        "model_base_url": "https://ai.example.com/v1",
        "duration_ms": 84200,
        "http_status": 200,
        "error_code": null,
        "error_message": null,
        "created_at": "2026-06-16T12:32:30Z"
      }
    ],
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

Важно:

- технические логи не должны хранить полный `raw_material`, если он уже сохранён в сообщениях;
- не хранить API key модели;
- можно хранить debug prompt только если это явно включено в настройках и доступно только админу.

## 13. Model health API

## 13.1. `GET /api/admin/model/health`

Проверяет доступность модели.

Доступ:

- только `admin`.

Поведение:

- endpoint делает короткий запрос к OpenAI-compatible API;
- использует настройки `model_base_url`, `model_name`, `model_api_key`;
- не должен запускать полноценную генерацию длинного текста.

Ответ при успехе:

```json
{
  "ok": true,
  "data": {
    "status": "ok",
    "model_base_url": "https://ai.example.com/v1",
    "model_name": "Qwen/Qwen3-32B",
    "duration_ms": 1200
  }
}
```

Ответ при ошибке:

```json
{
  "ok": false,
  "error": {
    "code": "model_error",
    "message": "Не удалось подключиться к модели.",
    "details": {
      "duration_ms": 5000
    }
  }
}
```

## 14. Queue API

В MVP отдельные публичные endpoints управления очередью не обязательны. Очередь должна быть видна через статусы `generation_jobs`.

Опционально для админа:

## 14.1. `GET /api/admin/generation-jobs`

Возвращает текущие и недавние задачи генерации.

Доступ:

- только `admin`.

Query parameters:

```txt
limit=50
offset=0
status=queued|running|completed|failed|cancelled
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": 55,
        "chat_id": 10,
        "user_id": 2,
        "username": "pr_manager",
        "mode": "new_article",
        "status": "running",
        "created_at": "2026-06-16T12:31:00Z",
        "started_at": "2026-06-16T12:31:05Z",
        "completed_at": null,
        "failed_at": null
      }
    ],
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

## 14.2. `POST /api/admin/generation-jobs/{job_id}/cancel`

Отменяет задачу, если она ещё не завершена.

Доступ:

- только `admin`.

Ответ:

```json
{
  "ok": true,
  "data": {
    "job_id": 55,
    "status": "cancelled",
    "message": "Задача отменена."
  }
}
```

Если задача уже отправлена во внешний model API, фактическую генерацию можно не прерывать физически, но результат не должен быть применён к чату, если job был отменён.

## 15. Структура ответа модели после генерации

Backend должен стараться привести ответ модели к единому виду.

Ожидаемый формат текста от модели:

```txt
ВАРИАНТЫ ЗАГОЛОВКОВ
1. ...
2. ...
3. ...

ЛИД
...

СТАТЬЯ
...

ВОПРОСЫ / УТОЧНЕНИЯ
...
```

Backend может хранить:

- `full_text` — полный ответ модели;
- `title_options` — массив заголовков, если удалось распарсить;
- `lead` — лид, если удалось распарсить;
- `body` — текст статьи, если удалось распарсить;
- `questions` — массив вопросов, если удалось распарсить.

Если распарсить строго не удалось, backend должен всё равно сохранить `full_text` как сообщение ассистента, но отметить в metadata:

```json
{
  "parse_status": "partial",
  "parse_error": "Не найден раздел ЛИД"
}
```

## 16. Поведение при нехватке фактов

Это не отдельный endpoint, но важный контракт генерации.

Если пользователь просит текст на 4000 символов, а фактов хватает только на 1000 символов, модель должна:

- написать текст меньшей длины;
- не выдумывать факты;
- не добавлять неподтверждённые даты, цифры, имена, должности, географию, цитаты;
- добавить вопросы в раздел `ВОПРОСЫ / УТОЧНЕНИЯ`.

UI должен показывать результат как успешный, а не как ошибку.

## 17. Поведение при просьбе добавить неизвестные факты

Если пользователь в режиме доработки просит добавить факт, которого нет в последней версии статьи или исходных данных, модель должна отказаться добавлять его как утверждение.

Пример пользовательской просьбы:

```txt
Добавь, что компания стала лидером рынка.
```

Если такого факта нет в исходных данных, ответ должен быть примерно таким:

```txt
Я не могу добавить утверждение о лидерстве компании без подтверждения в исходных данных. Укажите источник или добавьте этот факт явно, и я включу его в текст.
```

Backend не должен считать это ошибкой генерации.

## 18. HTTP status codes

Рекомендуемые статусы:

| Ситуация | HTTP status |
|---|---:|
| Успех | `200` |
| Создание сущности | `201` |
| Некорректный запрос | `400` |
| Не авторизован | `401` |
| Нет доступа | `403` |
| Не найдено | `404` |
| Конфликт, например активная генерация | `409` |
| Ошибка валидации | `422` |
| Ошибка сервера | `500` |
| Недоступна модель / внешний сервис | `502` или `503` |
| Таймаут модели | `504` |

Даже при ошибке тело JSON должно соответствовать единому формату ошибки.

## 19. Минимальный набор endpoints для MVP

Codex должен реализовать минимум:

### Пользовательская часть

```txt
GET  /
GET  /login
POST /login
POST /logout
GET  /chats
GET  /chats/{chat_id}
GET  /api/me
GET  /api/chats
POST /api/chats
GET  /api/chats/{chat_id}
GET  /api/chats/{chat_id}/messages
POST /api/chats/{chat_id}/generate
GET  /api/generation-jobs/{job_id}
POST /api/generation-jobs/{job_id}/retry
GET  /api/options/generation
POST /api/uploads/docx/extract
GET  /api/article-versions/{version_id}/download.txt
POST /api/article-versions/{version_id}/restore
```

### Админская часть

```txt
GET   /admin
GET   /api/admin/users
POST  /api/admin/users
PATCH /api/admin/users/{user_id}
POST  /api/admin/users/{user_id}/change-password
GET   /api/admin/chats
GET   /api/admin/settings
PATCH /api/admin/settings
GET   /api/admin/prompts/master
PUT   /api/admin/prompts/master
POST  /api/admin/prompts/preview
GET   /api/admin/generation-logs
GET   /api/admin/model/health
```

## 20. Не делать в MVP

В первой версии не нужно реализовывать:

- самостоятельную регистрацию пользователей;
- email;
- восстановление пароля через email;
- удаление диалогов;
- переименование диалогов;
- `.pdf` загрузку;
- `.docx` экспорт;
- CMS-интеграции;
- внешний фактчекинг;
- интернет-поиск;
- streaming ответа модели;
- React SPA;
- Docker;
- PostgreSQL;
- мультиязычность интерфейса;
- пользовательские стили;
- тонкие настройки температуры модели в UI.

## 21. OpenAI-compatible model API

Внутренний model adapter должен использовать OpenAI-compatible клиент.

Минимальная схема подключения:

```python
from openai import OpenAI

client = OpenAI(
    base_url=settings.MODEL_BASE_URL,
    api_key=settings.MODEL_API_KEY,
)

response = client.chat.completions.create(
    model=settings.MODEL_NAME,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    max_tokens=settings.MODEL_MAX_TOKENS,
    temperature=settings.MODEL_TEMPERATURE,
    top_p=settings.MODEL_TOP_P,
)

text = response.choices[0].message.content
```

Дефолтные значения для MVP:

```txt
MODEL_NAME=Qwen/Qwen3-32B
MODEL_MAX_TOKENS=3000
MODEL_TEMPERATURE=0.7
MODEL_TOP_P=0.8
GENERATION_TIMEOUT_SECONDS=180
```

`MODEL_BASE_URL` и `MODEL_API_KEY` задаются через `.env`.

## 22. Требования к безопасности API

- Все приватные endpoints должны проверять session.
- Все admin endpoints должны проверять роль `admin`.
- Пользователь не может получить чужой диалог через прямой URL.
- Пользователь не может скачать чужую статью через прямой URL.
- Пользователь не может читать чужие generation jobs.
- API key модели нельзя возвращать на frontend.
- Загруженный `.docx` удаляется после извлечения текста.
- Пароли хранятся только в хешированном виде.
- Нельзя заблокировать последнего активного администратора.

## 23. Критерии приёмки API

API считается реализованным корректно, если:

1. Пользователь может войти по логину и паролю.
2. Самостоятельная регистрация отсутствует.
3. Админ может создать пользователя.
4. Пользователь видит только свои диалоги.
5. Админ видит все диалоги с указанием пользователей.
6. Пользователь может создать диалог с обязательным названием.
7. Пользователь может отправить сырой материал и получить job id.
8. UI может poll-ить статус генерации.
9. После завершения генерации в чате появляется ответ ассистента.
10. Создаётся новая версия статьи.
11. Пользователь может доработать последнюю версию статьи.
12. Пользователь может откатиться к предыдущей версии.
13. Пользователь может загрузить `.docx`, получить извлечённый текст, а файл удаляется.
14. Пользователь может скачать `.txt`.
15. Лимит входного материала работает и берётся из настроек.
16. Технические логи генерации сохраняются.
17. Админ может редактировать мастер-промт.
18. Админ может смотреть debug preview полного промпта.
19. Модель вызывается через OpenAI-compatible API.
20. При ошибке модели пользователь получает понятное сообщение, а исходные данные не теряются.
