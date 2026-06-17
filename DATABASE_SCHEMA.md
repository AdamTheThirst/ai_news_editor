# DATABASE_SCHEMA.md

## 1. Назначение документа

Этот документ описывает структуру базы данных SQLite для проекта **AI-редактор новостных статей**.

Базу данных использует backend на FastAPI. В первой версии проекта применяется SQLite, потому что приложение разворачивается на одном VPS, рассчитано примерно на 30 пользователей и не требует отдельного сервера PostgreSQL.

Схема должна поддерживать:

- многопользовательский режим;
- роли `user` и `admin`;
- создание пользователей администратором;
- историю диалогов;
- сообщения пользователя и ИИ;
- последнюю версию статьи;
- историю версий статьи;
- генерационные задачи и их статусы;
- системные настройки;
- мастер-промпт;
- debug-просмотр полного промпта для администратора;
- технические логи запросов к модели;
- лимиты ввода;
- хранение извлечённого текста из `.docx` без сохранения самого файла.

---

## 2. Общие принципы

### 2.1. Формат времени

Все даты и время хранить в UTC в формате ISO 8601:

```text
YYYY-MM-DDTHH:MM:SSZ
```

Пример:

```text
2026-06-16T12:30:45Z
```

В Python лучше использовать timezone-aware `datetime`.

### 2.2. Первичные ключи

Для всех основных таблиц использовать целочисленные автоинкрементные ID:

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
```

### 2.3. Мягкое удаление

В первой версии удаление диалогов пользователем не требуется. Поэтому можно не делать `deleted_at` для чатов и сообщений.

Для пользователей нужен флаг блокировки:

```sql
is_active INTEGER NOT NULL DEFAULT 1
```

### 2.4. JSON-поля

SQLite допускает хранение JSON как `TEXT`. Для параметров генерации и служебных метаданных использовать `TEXT`, внутри которого лежит валидный JSON.

Примеры:

```json
{
  "tone": "neutral_news",
  "length_preset": "1200_1500",
  "composition": "inverted_pyramid",
  "paragraphs": 4
}
```

---

## 3. Список таблиц

Основные таблицы:

1. `users`
2. `sessions`
3. `chats`
4. `messages`
5. `article_versions`
6. `generation_jobs`
7. `app_settings`
8. `prompt_templates`
9. `model_request_logs`
10. `uploaded_documents`
11. `audit_logs`

---

## 4. Таблица `users`

Хранит пользователей системы.

Пользователей создаёт только администратор. Самостоятельная публичная регистрация в первой версии не нужна.

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER | ID пользователя |
| `username` | TEXT | Логин пользователя |
| `password_hash` | TEXT | Хеш пароля |
| `role` | TEXT | `user` или `admin` |
| `is_active` | INTEGER | `1` — активен, `0` — заблокирован |
| `created_at` | TEXT | Дата создания |
| `updated_at` | TEXT | Дата обновления |
| `last_login_at` | TEXT | Последний вход |

### Ограничения

```sql
CHECK (role IN ('user', 'admin'))
```

Можно добавить сразу в DDL:

```sql
role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin'))
```

### Индексы

```sql
CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);
```

---

## 5. Таблица `sessions`

Хранит серверные пользовательские сессии.

Если будет использоваться cookie-session без серверного хранения, таблица необязательна. Но для нормального контроля сессий на VPS лучше хранить их в базе.

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT,
    user_agent TEXT,
    ip_address TEXT,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER | Владелец сессии |
| `session_token_hash` | TEXT | Хеш токена сессии, не сам токен |
| `expires_at` | TEXT | Время истечения сессии |
| `is_revoked` | INTEGER | Сессия принудительно отозвана |

### Индексы

```sql
CREATE UNIQUE INDEX idx_sessions_token_hash ON sessions(session_token_hash);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

---

## 6. Таблица `chats`

Хранит диалоги пользователей.

Название диалога — обязательное поле, которое пользователь вводит перед первой генерацией.

```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    context TEXT,
    latest_article_version_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (latest_article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER | Владелец диалога |
| `title` | TEXT | Обязательное название диалога |
| `context` | TEXT | Опциональный контекст от пользователя |
| `latest_article_version_id` | INTEGER | Последняя актуальная версия статьи |
| `archived_at` | TEXT | Для будущей архивации, если понадобится |

### Важное поведение

- Обычный пользователь видит только свои `chats`.
- Администратор видит все `chats` с указанием пользователя.
- В первой версии пользователь не переименовывает и не удаляет чаты.

### Индексы

```sql
CREATE INDEX idx_chats_user_id ON chats(user_id);
CREATE INDEX idx_chats_updated_at ON chats(updated_at);
CREATE INDEX idx_chats_user_updated ON chats(user_id, updated_at);
```

---

## 7. Таблица `messages`

Хранит сообщения внутри диалога.

Сюда попадают:

- исходный материал пользователя;
- пользовательские просьбы о доработке;
- ответы ИИ;
- системные сообщения приложения, если нужно показать ошибку или предупреждение в чате.

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'chat',
    generation_job_id INTEGER,
    article_version_id INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `chat_id` | INTEGER | Диалог |
| `user_id` | INTEGER | Автор сообщения, если это пользователь |
| `role` | TEXT | `user`, `assistant`, `system` |
| `content` | TEXT | Текст сообщения |
| `message_type` | TEXT | Тип сообщения |
| `generation_job_id` | INTEGER | Связь с задачей генерации |
| `article_version_id` | INTEGER | Связь с версией статьи |
| `metadata_json` | TEXT | Дополнительные данные |

### Возможные значения `role`

```text
user
assistant
system
```

### Возможные значения `message_type`

```text
chat
initial_material
revision_request
article_output
warning
error
```

### Пример `metadata_json` для исходного материала

```json
{
  "source": "manual",
  "input_chars": 3420,
  "has_context": true
}
```

### Пример `metadata_json` для `.docx`

```json
{
  "source": "docx",
  "original_filename": "facts.docx",
  "extracted_chars": 2860,
  "file_saved": false
}
```

### Индексы

```sql
CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_chat_created ON messages(chat_id, created_at);
CREATE INDEX idx_messages_generation_job_id ON messages(generation_job_id);
```

---

## 8. Таблица `article_versions`

Хранит версии статьи.

Каждая новая генерация или доработка создаёт новую версию статьи. Последняя версия связывается с `chats.latest_article_version_id`.

Это позволяет:

- показывать пользователю актуальную статью;
- откатиться к предыдущей версии;
- дать ИИ контекст последней версии при доработке;
- не терять результат, если пользователь продолжает диалог.

```sql
CREATE TABLE article_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    title_options_json TEXT NOT NULL,
    selected_title TEXT,
    lead TEXT NOT NULL,
    body TEXT NOT NULL,
    questions TEXT,
    generation_params_json TEXT NOT NULL,
    source_message_id INTEGER,
    generation_job_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    UNIQUE(chat_id, version_number)
);
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `chat_id` | INTEGER | Диалог |
| `version_number` | INTEGER | Номер версии внутри диалога |
| `title_options_json` | TEXT | JSON-массив вариантов заголовка |
| `selected_title` | TEXT | Выбранный/основной заголовок |
| `lead` | TEXT | Лид статьи |
| `body` | TEXT | Основной текст статьи |
| `questions` | TEXT | Вопросы к пользователю, если данных не хватает |
| `generation_params_json` | TEXT | Параметры генерации |
| `source_message_id` | INTEGER | Сообщение, из которого создана версия |
| `generation_job_id` | INTEGER | Задача генерации |

### Пример `title_options_json`

```json
[
  "Компания представила новый сервис для клиентов",
  "Новый сервис компании должен ускорить обработку заявок",
  "Компания запустила инструмент для работы с клиентскими обращениями"
]
```

### Пример `generation_params_json`

```json
{
  "tone": "neutral_news",
  "tone_label": "Нейтрально-новостной",
  "composition": "inverted_pyramid",
  "composition_label": "Перевёрнутая пирамида",
  "length_preset": "1200_1500",
  "target_min_chars": 1200,
  "target_max_chars": 1500,
  "paragraphs": 4,
  "no_cta": true,
  "strict_source_only": true
}
```

### Индексы

```sql
CREATE INDEX idx_article_versions_chat_id ON article_versions(chat_id);
CREATE INDEX idx_article_versions_chat_version ON article_versions(chat_id, version_number);
CREATE INDEX idx_article_versions_created_at ON article_versions(created_at);
```

---

## 9. Таблица `generation_jobs`

Хранит задачи генерации и доработки.

Нужна для очереди, статусов, ожидания ответа модели и повторов после ошибки.

```sql
CREATE TABLE generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    input_message_id INTEGER,
    output_message_id INTEGER,
    article_version_id INTEGER,
    generation_params_json TEXT NOT NULL,
    prompt_snapshot TEXT,
    error_message TEXT,
    model_name TEXT,
    model_base_url TEXT,
    input_chars INTEGER,
    requested_min_chars INTEGER,
    requested_max_chars INTEGER,
    output_chars INTEGER,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (input_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (output_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);
```

### Возможные значения `job_type`

```text
initial_article
revision
retry
```

### Возможные значения `status`

```text
queued
running
succeeded
failed
timeout
cancelled
```

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `job_type` | TEXT | Первичная генерация, доработка или повтор |
| `status` | TEXT | Статус задачи |
| `generation_params_json` | TEXT | Параметры генерации |
| `prompt_snapshot` | TEXT | Полный промпт, доступен только админу |
| `error_message` | TEXT | Текст ошибки |
| `model_name` | TEXT | Например `Qwen/Qwen3-32B` |
| `model_base_url` | TEXT | Base URL OpenAI-compatible API |
| `input_chars` | INTEGER | Символов во входе |
| `output_chars` | INTEGER | Символов в ответе |

### Ограничение активной генерации пользователя

На уровне приложения нужно не разрешать пользователю создавать новую задачу, если у него уже есть задача со статусом:

```text
queued
running
```

В SQLite частичный уникальный индекс можно сделать так:

```sql
CREATE UNIQUE INDEX idx_generation_jobs_one_active_per_user
ON generation_jobs(user_id)
WHERE status IN ('queued', 'running');
```

### Индексы

```sql
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_generation_jobs_user_id ON generation_jobs(user_id);
CREATE INDEX idx_generation_jobs_chat_id ON generation_jobs(chat_id);
CREATE INDEX idx_generation_jobs_queued_at ON generation_jobs(queued_at);
CREATE INDEX idx_generation_jobs_status_queued ON generation_jobs(status, queued_at);
```

---

## 10. Таблица `app_settings`

Хранит системные настройки, доступные администратору.

```sql
CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string',
    description TEXT,
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_by_user_id INTEGER,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

### Примеры настроек

| key | value | value_type | Описание |
|---|---|---|---|
| `max_input_chars` | `5000` | `integer` | Максимальный размер исходного материала |
| `default_length_preset` | `1200_1500` | `string` | Длина по умолчанию |
| `default_paragraphs` | `4` | `integer` | Количество абзацев по умолчанию |
| `generation_timeout_seconds` | `180` | `integer` | Таймаут запроса к модели |
| `max_concurrent_generation_jobs` | `2` | `integer` | Сколько генераций можно выполнять одновременно |
| `model_base_url` | `https://ai...` | `string` | URL vLLM сервера |
| `model_name` | `Qwen/Qwen3-32B` | `string` | Имя модели |
| `model_api_key` | `sk-...` | `string` | API-ключ, секретное значение |
| `model_max_tokens` | `2000` | `integer` | Максимум токенов ответа |
| `model_temperature` | `0.7` | `float` | Температура модели |
| `model_top_p` | `0.8` | `float` | top_p модели |
| `debug_prompt_enabled` | `1` | `boolean` | Показывать полный промпт админу |

### Секреты

`model_api_key` хранится в `app_settings` только если это явно удобно для админки. Более безопасный вариант — хранить ключ в `.env`, а в базе хранить только несекретные настройки.

Рекомендуемое решение для MVP:

- `MODEL_API_KEY` хранить в `.env`;
- в админке показывать только факт, что ключ задан;
- не отображать сам ключ в UI.

---

## 11. Таблица `prompt_templates`

Хранит мастер-промпт и, при необходимости, дополнительные промптовые блоки.

Мастер-промпт редактируется через админку.

```sql
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    template_type TEXT NOT NULL,
    content TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_user_id INTEGER,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

### Возможные значения `template_type`

```text
master
composition_block
tone_block
revision_block
system
```

### Минимальные шаблоны первой версии

| name | template_type | Назначение |
|---|---|---|
| `main_master_prompt` | `master` | Основной мастер-промпт |
| `revision_prompt` | `revision_block` | Инструкция для доработки последней версии статьи |

### Переменные подстановки

Мастер-промпт должен поддерживать переменные:

```text
{tone}
{composition}
{composition_description}
{target_min_chars}
{target_max_chars}
{paragraphs}
{dialog_title}
{context}
{source_material}
{latest_article}
{user_revision_request}
```

---

## 12. Таблица `model_request_logs`

Хранит технические логи запросов к модели.

Полный текст входа и выхода здесь хранить не нужно, потому что сообщения и версии статей уже есть в базе. Но `prompt_snapshot` хранится в `generation_jobs` для debug-режима администратора.

```sql
CREATE TABLE model_request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_job_id INTEGER,
    user_id INTEGER,
    chat_id INTEGER,
    model_name TEXT,
    model_base_url TEXT,
    request_started_at TEXT NOT NULL,
    request_finished_at TEXT,
    duration_ms INTEGER,
    http_status INTEGER,
    success INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    input_chars INTEGER,
    output_chars INTEGER,
    max_tokens INTEGER,
    temperature REAL,
    top_p REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL
);
```

### Что логировать

Логировать:

- user ID;
- chat ID;
- job ID;
- имя модели;
- base URL без секретов;
- время старта и окончания запроса;
- длительность;
- HTTP-статус;
- ошибку, если она была;
- размер входа и выхода;
- параметры модели.

Не логировать:

- API-ключ;
- пароль пользователя;
- cookie/session token;
- полный текст исходного материала отдельно от сообщений;
- полный ответ модели отдельно от `messages` / `article_versions`.

### Индексы

```sql
CREATE INDEX idx_model_request_logs_job_id ON model_request_logs(generation_job_id);
CREATE INDEX idx_model_request_logs_user_id ON model_request_logs(user_id);
CREATE INDEX idx_model_request_logs_chat_id ON model_request_logs(chat_id);
CREATE INDEX idx_model_request_logs_created_at ON model_request_logs(created_at);
CREATE INDEX idx_model_request_logs_success ON model_request_logs(success);
```

---

## 13. Таблица `uploaded_documents`

Хранит метаданные загруженных `.docx`.

Сам файл после извлечения текста удаляется. В базе сохраняются только метаданные и извлечённый текст в `messages.content`.

```sql
CREATE TABLE uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER,
    message_id INTEGER,
    original_filename TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    mime_type TEXT,
    file_size_bytes INTEGER,
    extracted_chars INTEGER,
    processing_status TEXT NOT NULL DEFAULT 'processed',
    error_message TEXT,
    file_saved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
);
```

### Возможные значения `processing_status`

```text
processed
failed
rejected_too_large
unsupported_format
```

### Индексы

```sql
CREATE INDEX idx_uploaded_documents_user_id ON uploaded_documents(user_id);
CREATE INDEX idx_uploaded_documents_chat_id ON uploaded_documents(chat_id);
CREATE INDEX idx_uploaded_documents_message_id ON uploaded_documents(message_id);
CREATE INDEX idx_uploaded_documents_created_at ON uploaded_documents(created_at);
```

---

## 14. Таблица `audit_logs`

Хранит действия администратора и важные системные события.

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    details_json TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

### Что логировать

- создание пользователя;
- блокировку пользователя;
- смену пароля пользователя;
- изменение мастер-промпта;
- изменение лимитов;
- изменение настроек модели;
- просмотр debug-промпта администратором;
- ошибки миграций, если они выводятся в приложение.

### Пример `details_json`

```json
{
  "changed_fields": ["max_input_chars", "default_length_preset"],
  "old_values": {
    "max_input_chars": "5000"
  },
  "new_values": {
    "max_input_chars": "7000"
  }
}
```

### Индексы

```sql
CREATE INDEX idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

---

## 15. Связи между таблицами

```text
users 1 ─── * chats
users 1 ─── * messages
users 1 ─── * generation_jobs
users 1 ─── * sessions

chats 1 ─── * messages
chats 1 ─── * article_versions
chats 1 ─── * generation_jobs

messages * ─── 0..1 generation_jobs
messages * ─── 0..1 article_versions

generation_jobs 1 ─── 0..1 article_versions
generation_jobs 1 ─── * model_request_logs

prompt_templates * ─── 0..1 users через updated_by_user_id
app_settings * ─── 0..1 users через updated_by_user_id
```

---

## 16. Начальные данные

При первом запуске приложение должно создать:

1. первого администратора;
2. базовые настройки;
3. стандартный мастер-промпт;
4. стандартный промпт для доработки;
5. справочник стилей и композиций в коде или настройках.

### 16.1. Первый администратор

Вариант для MVP:

- при первом запуске backend читает из `.env`:
  - `INITIAL_ADMIN_USERNAME`
  - `INITIAL_ADMIN_PASSWORD`
- если в таблице `users` нет ни одного администратора, создаёт его;
- после создания пароль в логах не печатать.

### 16.2. Базовые настройки

```sql
INSERT INTO app_settings (key, value, value_type, description, is_secret, updated_at)
VALUES
('max_input_chars', '5000', 'integer', 'Максимальная длина исходного материала в символах', 0, CURRENT_TIMESTAMP),
('default_length_preset', '1200_1500', 'string', 'Диапазон длины статьи по умолчанию', 0, CURRENT_TIMESTAMP),
('default_paragraphs', '4', 'integer', 'Количество абзацев по умолчанию', 0, CURRENT_TIMESTAMP),
('generation_timeout_seconds', '180', 'integer', 'Таймаут запроса к модели', 0, CURRENT_TIMESTAMP),
('max_concurrent_generation_jobs', '2', 'integer', 'Максимальное количество одновременных генераций', 0, CURRENT_TIMESTAMP),
('model_base_url', '', 'string', 'Base URL OpenAI-compatible vLLM API', 0, CURRENT_TIMESTAMP),
('model_name', 'Qwen/Qwen3-32B', 'string', 'Имя модели для chat completions', 0, CURRENT_TIMESTAMP),
('model_max_tokens', '2000', 'integer', 'Максимальное количество токенов ответа', 0, CURRENT_TIMESTAMP),
('model_temperature', '0.7', 'float', 'Temperature для модели', 0, CURRENT_TIMESTAMP),
('model_top_p', '0.8', 'float', 'Top-p для модели', 0, CURRENT_TIMESTAMP),
('debug_prompt_enabled', '1', 'boolean', 'Показывать полный промпт администратору', 0, CURRENT_TIMESTAMP);
```

---

## 17. Справочники в коде

Чтобы не усложнять первую версию, стили, длины и композиции можно хранить в коде как константы. В базу сохраняются только выбранные значения в `generation_params_json`.

### 17.1. Стили

```python
ARTICLE_TONES = {
    "neutral_news": "Нейтрально-новостной",
    "business": "Деловой",
    "light_magazine": "Лёгкий журнальный",
    "human_interest": "Human interest",
}
```

### 17.2. Длины

```python
LENGTH_PRESETS = {
    "800_1500": {"label": "800–1500 символов", "min": 800, "max": 1500},
    "1501_2500": {"label": "1501–2500 символов", "min": 1501, "max": 2500},
    "2501_4000": {"label": "2501–4000 символов", "min": 2501, "max": 4000},
    "1200_1500": {"label": "1200–1500 символов", "min": 1200, "max": 1500},
}
```

`1200_1500` — значение по умолчанию.

### 17.3. Композиции

```python
ARTICLE_COMPOSITIONS = {
    "inverted_pyramid": "Перевёрнутая пирамида",
    "chronological": "Хронологическая структура",
    "fact_context_consequences": "Факт → контекст → последствия",
    "problem_reaction_consequences": "Проблема → реакция → последствия",
    "human_interest": "Human interest",
    "explainer": "Explainer / объясняющая структура",
    "aida_no_cta": "AIDA без CTA",
}
```

---

## 18. Миграции

Для MVP допустим один из вариантов:

### Вариант A: простой SQL-файл

Создать файл:

```text
app/db/schema.sql
```

При старте приложения проверять наличие таблиц и создавать их, если их нет.

Подходит для самой первой версии.

### Вариант B: Alembic

Если Codex сразу делает более аккуратную архитектуру, можно использовать Alembic.

Рекомендуемый вариант для проекта:

- использовать SQLAlchemy ORM;
- подключить Alembic;
- создать первую миграцию `initial_schema`;
- все изменения схемы делать через миграции.

Для Codex предпочтительно использовать **SQLAlchemy + Alembic**, потому что проект многопользовательский и будет развиваться.

---

## 19. Минимальная ORM-структура

Рекомендуемая структура моделей:

```text
app/models/user.py
app/models/session.py
app/models/chat.py
app/models/message.py
app/models/article_version.py
app/models/generation_job.py
app/models/app_setting.py
app/models/prompt_template.py
app/models/model_request_log.py
app/models/uploaded_document.py
app/models/audit_log.py
```

Можно также собрать все модели в одном файле `app/models.py` на первой итерации, но для поддержки лучше разделить.

---

## 20. Правила доступа к данным

### 20.1. Обычный пользователь

Обычный пользователь может:

- видеть только свои чаты;
- видеть только свои сообщения;
- создавать новые чаты;
- отправлять материал;
- запускать генерацию;
- отправлять просьбы о доработке;
- скачивать TXT только своих статей;
- откатываться к предыдущей версии только в своих чатах.

Обычный пользователь не может:

- видеть чужие чаты;
- видеть debug-промпты;
- менять мастер-промпт;
- менять системные настройки;
- создавать пользователей;
- блокировать пользователей.

### 20.2. Администратор

Администратор может:

- видеть все чаты всех пользователей;
- видеть имя пользователя рядом с каждым диалогом;
- открывать чужие диалоги в режиме просмотра;
- видеть полный prompt snapshot, если debug включён;
- создавать пользователей;
- блокировать пользователей;
- менять пароль пользователям;
- редактировать мастер-промпт;
- менять лимит исходного материала;
- менять системные настройки генерации;
- видеть технические логи модели.

---

## 21. Генерация и версии статьи

### 21.1. Первичная генерация

При первичной генерации приложение создаёт:

1. `chat`;
2. `message` с `message_type = initial_material`;
3. `generation_job` со статусом `queued`;
4. после успешного ответа модели:
   - `article_versions` с `version_number = 1`;
   - `message` с `message_type = article_output`;
   - обновляет `chats.latest_article_version_id`;
   - обновляет `generation_jobs.status = succeeded`.

### 21.2. Доработка

При доработке приложение:

1. берёт `chats.latest_article_version_id`;
2. создаёт `message` с `message_type = revision_request`;
3. создаёт `generation_job` с `job_type = revision`;
4. в промпт передаёт:
   - последнюю версию статьи;
   - просьбу пользователя;
   - ограничение не добавлять неподтверждённые факты;
5. после успешного ответа создаёт новую `article_versions` с `version_number + 1`;
6. обновляет `chats.latest_article_version_id`.

### 21.3. Откат

Откат к предыдущей версии можно реализовать двумя способами.

Рекомендуемый способ:

- не удалять версии;
- при откате установить `chats.latest_article_version_id` на предыдущую версию;
- добавить системное сообщение в чат: `Выполнен откат к версии N`.

---

## 22. Резервное копирование SQLite

Так как приложение хранит рабочие материалы пользователей, нужно предусмотреть backup.

Минимальная рекомендация для `DEPLOYMENT.md`:

```bash
sqlite3 app.db ".backup 'backup/app-$(date +%F-%H%M).db'"
```

Бэкап можно выполнять через cron.

---

## 23. Полный SQL-скелет

Codex может использовать этот раздел как стартовый `schema.sql`. При использовании SQLAlchemy/Alembic этот SQL нужно перенести в ORM-модели и миграции.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT,
    user_agent TEXT,
    ip_address TEXT,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    context TEXT,
    latest_article_version_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (latest_article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'chat',
    generation_job_id INTEGER,
    article_version_id INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);

CREATE TABLE article_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    title_options_json TEXT NOT NULL,
    selected_title TEXT,
    lead TEXT NOT NULL,
    body TEXT NOT NULL,
    questions TEXT,
    generation_params_json TEXT NOT NULL,
    source_message_id INTEGER,
    generation_job_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    UNIQUE(chat_id, version_number)
);

CREATE TABLE generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    job_type TEXT NOT NULL CHECK (job_type IN ('initial_article', 'revision', 'retry')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'timeout', 'cancelled')),
    input_message_id INTEGER,
    output_message_id INTEGER,
    article_version_id INTEGER,
    generation_params_json TEXT NOT NULL,
    prompt_snapshot TEXT,
    error_message TEXT,
    model_name TEXT,
    model_base_url TEXT,
    input_chars INTEGER,
    requested_min_chars INTEGER,
    requested_max_chars INTEGER,
    output_chars INTEGER,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (input_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (output_message_id) REFERENCES messages(id) ON DELETE SET NULL,
    FOREIGN KEY (article_version_id) REFERENCES article_versions(id) ON DELETE SET NULL
);

CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string',
    description TEXT,
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_by_user_id INTEGER,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    template_type TEXT NOT NULL,
    content TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_user_id INTEGER,
    FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE model_request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_job_id INTEGER,
    user_id INTEGER,
    chat_id INTEGER,
    model_name TEXT,
    model_base_url TEXT,
    request_started_at TEXT NOT NULL,
    request_finished_at TEXT,
    duration_ms INTEGER,
    http_status INTEGER,
    success INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    input_chars INTEGER,
    output_chars INTEGER,
    max_tokens INTEGER,
    temperature REAL,
    top_p REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL
);

CREATE TABLE uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    chat_id INTEGER,
    message_id INTEGER,
    original_filename TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    mime_type TEXT,
    file_size_bytes INTEGER,
    extracted_chars INTEGER,
    processing_status TEXT NOT NULL DEFAULT 'processed',
    error_message TEXT,
    file_saved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE SET NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    details_json TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_is_active ON users(is_active);

CREATE UNIQUE INDEX idx_sessions_token_hash ON sessions(session_token_hash);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);

CREATE INDEX idx_chats_user_id ON chats(user_id);
CREATE INDEX idx_chats_updated_at ON chats(updated_at);
CREATE INDEX idx_chats_user_updated ON chats(user_id, updated_at);

CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_chat_created ON messages(chat_id, created_at);
CREATE INDEX idx_messages_generation_job_id ON messages(generation_job_id);

CREATE INDEX idx_article_versions_chat_id ON article_versions(chat_id);
CREATE INDEX idx_article_versions_chat_version ON article_versions(chat_id, version_number);
CREATE INDEX idx_article_versions_created_at ON article_versions(created_at);

CREATE INDEX idx_generation_jobs_status ON generation_jobs(status);
CREATE INDEX idx_generation_jobs_user_id ON generation_jobs(user_id);
CREATE INDEX idx_generation_jobs_chat_id ON generation_jobs(chat_id);
CREATE INDEX idx_generation_jobs_queued_at ON generation_jobs(queued_at);
CREATE INDEX idx_generation_jobs_status_queued ON generation_jobs(status, queued_at);
CREATE UNIQUE INDEX idx_generation_jobs_one_active_per_user
ON generation_jobs(user_id)
WHERE status IN ('queued', 'running');

CREATE INDEX idx_model_request_logs_job_id ON model_request_logs(generation_job_id);
CREATE INDEX idx_model_request_logs_user_id ON model_request_logs(user_id);
CREATE INDEX idx_model_request_logs_chat_id ON model_request_logs(chat_id);
CREATE INDEX idx_model_request_logs_created_at ON model_request_logs(created_at);
CREATE INDEX idx_model_request_logs_success ON model_request_logs(success);

CREATE INDEX idx_uploaded_documents_user_id ON uploaded_documents(user_id);
CREATE INDEX idx_uploaded_documents_chat_id ON uploaded_documents(chat_id);
CREATE INDEX idx_uploaded_documents_message_id ON uploaded_documents(message_id);
CREATE INDEX idx_uploaded_documents_created_at ON uploaded_documents(created_at);

CREATE INDEX idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

---

## 24. Важное замечание по циклическим внешним ключам

В схеме есть логическая связь:

- `chats.latest_article_version_id` ссылается на `article_versions.id`;
- `article_versions.chat_id` ссылается на `chats.id`.

Это допустимо, но при создании таблиц и миграций через ORM может потребовать аккуратной настройки.

Если Codex столкнётся с проблемой циклических зависимостей, можно упростить:

- оставить `latest_article_version_id` как обычное INTEGER-поле без физического foreign key;
- проверять корректность на уровне приложения.

Для MVP это приемлемо.

---

## 25. Критерии готовности схемы

Схема считается реализованной, если:

1. Приложение создаёт SQLite-базу при первом запуске.
2. Первый администратор создаётся из `.env`, если админов ещё нет.
3. Пароли пользователей хранятся только в виде хеша.
4. Обычный пользователь видит только свои диалоги.
5. Администратор видит все диалоги с указанием пользователей.
6. Создание статьи сохраняет чат, исходный материал, job, ответ ИИ и первую версию статьи.
7. Доработка статьи создаёт новую версию.
8. Последняя версия статьи доступна для дальнейшей доработки.
9. Можно откатиться к предыдущей версии.
10. `.docx` после извлечения текста не сохраняется как файл.
11. Технические логи запросов к модели сохраняются.
12. Мастер-промпт и системные настройки редактируются через админку.
13. Debug-промпт доступен только администратору.
14. В базе есть индексы для основных списков: чаты, сообщения, jobs, логи.
