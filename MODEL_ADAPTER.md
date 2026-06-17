# MODEL_ADAPTER.md

## 1. Назначение документа

Этот документ описывает слой подключения приложения к локальной/частной LLM-модели Qwen, развёрнутой через vLLM и доступной по OpenAI-compatible API.

Документ предназначен для Codex и должен использоваться при реализации:

- клиента модели;
- конфигурации подключения;
- вызова `chat.completions.create`;
- обработки ошибок модели;
- таймаутов;
- логирования технических параметров генерации;
- изоляции backend-кода от конкретного API модели;
- возможности позже заменить модель или endpoint без переписывания бизнес-логики.

---

## 2. Исходные данные по модели

Модель доступна через OpenAI-compatible API.

Минимальный пример подключения, предоставленный заказчиком:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://ai...",  # URL vLLM сервера
    api_key="sk-...."
)

try:
    chat_response = client.chat.completions.create(
        model="Qwen/Qwen3-32B",
        messages=[
            {"role": "system", "content": "Вы - опытный финансовый аналитик."},
            {"role": "user", "content": "Чем должно быть подкреплено профессиональное суждение по резервам?"}
        ],
        max_tokens=200,
        temperature=0.7,
        top_p=0.8
    )

    print("\nОтвет (chat completion):")
    print(chat_response.choices[0].message.content)

except Exception as chat_error:
    print(f"Ошибка при chat completion запросе: {chat_error}")
```

В MVP приложение должно использовать этот же тип подключения, но параметры должны быть вынесены в конфигурацию.

---

## 3. Принцип архитектуры

Весь код работы с моделью должен быть изолирован в отдельном модуле.

Рекомендуемый модуль:

```text
app/services/model_adapter.py
```

Backend не должен напрямую вызывать `OpenAI(...)` в роутерах, задачах генерации или UI-слое.

Правильная схема:

```text
FastAPI route / service
        ↓
Generation service
        ↓
Prompt builder
        ↓
Model adapter
        ↓
vLLM / OpenAI-compatible API
```

Это позволит:

- заменить модель без переписывания роутов;
- централизованно обрабатывать ошибки;
- централизованно логировать длительность и технические параметры;
- переиспользовать адаптер для первичной генерации и доработки статьи;
- позже добавить другой backend модели, например OpenAI, Ollama, llama.cpp server или другой vLLM endpoint.

---

## 4. Переменные окружения

Параметры подключения не должны храниться в коде.

Использовать `.env`.

Минимальный набор:

```env
MODEL_PROVIDER=openai_compatible
MODEL_BASE_URL=https://ai.example.com/v1
MODEL_API_KEY=sk-change-me
MODEL_NAME=Qwen/Qwen3-32B
MODEL_TIMEOUT_SECONDS=180
MODEL_MAX_TOKENS=2500
MODEL_TEMPERATURE=0.4
MODEL_TOP_P=0.8
MODEL_MAX_RETRIES=1
```

### 4.1. Описание переменных

| Переменная | Обязательна | Значение по умолчанию | Описание |
|---|---:|---:|---|
| `MODEL_PROVIDER` | да | `openai_compatible` | Тип провайдера модели. В MVP поддерживается только `openai_compatible`. |
| `MODEL_BASE_URL` | да | нет | URL vLLM/OpenAI-compatible сервера. |
| `MODEL_API_KEY` | да | нет | Токен авторизации. |
| `MODEL_NAME` | да | `Qwen/Qwen3-32B` | Имя модели, которое передаётся в `chat.completions.create`. |
| `MODEL_TIMEOUT_SECONDS` | нет | `180` | Таймаут одного запроса к модели. |
| `MODEL_MAX_TOKENS` | нет | `2500` | Максимум токенов ответа. |
| `MODEL_TEMPERATURE` | нет | `0.4` | Температура генерации. |
| `MODEL_TOP_P` | нет | `0.8` | Значение `top_p`. |
| `MODEL_MAX_RETRIES` | нет | `1` | Количество повторных попыток после технической ошибки. |

---

## 5. Требования к безопасности

Запрещено:

- коммитить реальный `MODEL_API_KEY` в репозиторий;
- показывать API key в админке обычным текстом;
- писать API key в технические логи;
- возвращать API key в JSON-ответах backend;
- показывать обычным пользователям полный prompt;
- показывать обычным пользователям stack trace ошибок модели.

Допускается:

- хранить endpoint и имя модели в `.env`;
- показывать администратору имя модели;
- показывать администратору debug-prompt;
- показывать администратору техническую ошибку без секретов.

---

## 6. Рекомендуемая структура классов

### 6.1. DTO для запроса

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class ModelMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class ModelRequest:
    messages: list[ModelMessage]
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    request_id: str | None = None
```

### 6.2. DTO для ответа

```python
from dataclasses import dataclass


@dataclass
class ModelResponse:
    content: str
    model_name: str
    duration_ms: int
    raw_finish_reason: str | None = None
    raw_usage: dict | None = None
```

### 6.3. Исключение адаптера

```python
class ModelAdapterError(Exception):
    def __init__(self, message: str, *, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
```

---

## 7. Интерфейс адаптера

Реализовать класс `OpenAICompatibleModelAdapter`.

```python
class OpenAICompatibleModelAdapter:
    def __init__(self, settings: Settings):
        ...

    async def complete(self, request: ModelRequest) -> ModelResponse:
        ...
```

Для MVP допустима синхронная реализация внутри background task, но публичный интерфейс лучше сделать `async`, чтобы позже было проще перейти на async-клиент.

Если используется синхронный клиент `openai.OpenAI`, вызов модели внутри async-кода нужно выполнять через threadpool, чтобы не блокировать event loop FastAPI.

Пример:

```python
from starlette.concurrency import run_in_threadpool

response = await run_in_threadpool(self._complete_sync, request)
```

---

## 8. Инициализация клиента

```python
from openai import OpenAI


class OpenAICompatibleModelAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            timeout=settings.model_timeout_seconds,
        )
```

`settings` должен приходить из единого конфигурационного слоя приложения.

Рекомендуемый файл:

```text
app/core/config.py
```

---

## 9. Базовая реализация вызова модели

```python
import time
from starlette.concurrency import run_in_threadpool


class OpenAICompatibleModelAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            timeout=settings.model_timeout_seconds,
        )

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return await run_in_threadpool(self._complete_sync, request)

    def _complete_sync(self, request: ModelRequest) -> ModelResponse:
        started_at = time.monotonic()

        try:
            response = self.client.chat.completions.create(
                model=self.settings.model_name,
                messages=[
                    {"role": message.role, "content": message.content}
                    for message in request.messages
                ],
                max_tokens=request.max_tokens or self.settings.model_max_tokens,
                temperature=(
                    request.temperature
                    if request.temperature is not None
                    else self.settings.model_temperature
                ),
                top_p=request.top_p if request.top_p is not None else self.settings.model_top_p,
            )
        except Exception as exc:
            raise ModelAdapterError(
                "Не удалось получить ответ от языковой модели.",
                original_error=exc,
            ) from exc

        duration_ms = int((time.monotonic() - started_at) * 1000)

        if not response.choices:
            raise ModelAdapterError("Модель вернула пустой список choices.")

        message = response.choices[0].message
        content = (message.content or "").strip()

        if not content:
            raise ModelAdapterError("Модель вернула пустой ответ.")

        usage = None
        if getattr(response, "usage", None):
            usage = response.usage.model_dump() if hasattr(response.usage, "model_dump") else dict(response.usage)

        finish_reason = getattr(response.choices[0], "finish_reason", None)

        return ModelResponse(
            content=content,
            model_name=self.settings.model_name,
            duration_ms=duration_ms,
            raw_finish_reason=finish_reason,
            raw_usage=usage,
        )
```

---

## 10. Повторные попытки

В MVP достаточно одной повторной попытки после технической ошибки.

Повторять можно только ошибки транспортного уровня:

- timeout;
- temporary connection error;
- HTTP 502/503/504;
- временная недоступность vLLM.

Не нужно повторять:

- 401 Unauthorized;
- 403 Forbidden;
- 400 Bad Request;
- ошибки валидации промпта;
- слишком большой контекст;
- пустой пользовательский материал.

Пример поведения:

```text
MODEL_MAX_RETRIES=1
```

Это означает: один основной запрос + одна повторная попытка.

---

## 11. Таймауты

Таймаут по умолчанию: `180` секунд.

Если таймаут истёк:

1. job получает статус `failed`;
2. пользователю показывается понятная ошибка;
3. исходный материал и параметры остаются сохранёнными;
4. пользователь может нажать «Повторить»;
5. техническая ошибка записывается в лог.

Пользовательский текст ошибки:

```text
Не удалось получить ответ от модели: истекло время ожидания. Исходный материал и настройки сохранены. Попробуйте повторить генерацию.
```

---

## 12. Не использовать streaming в MVP

Заказчик подтвердил, что в MVP можно ждать полный ответ.

Поэтому:

- не реализовывать streaming tokens;
- не использовать server-sent events для токенов;
- UI показывает состояние «ИИ думает…»;
- backend создаёт generation job;
- frontend периодически опрашивает статус job.

Streaming можно добавить позже, не меняя prompt builder и основную бизнес-логику.

---

## 13. Интеграция с очередью генерации

Model adapter не должен сам управлять очередью.

Очередь реализуется выше, в generation service.

Схема:

```text
POST /api/chats/{chat_id}/generate
        ↓
создание generation_job со статусом queued
        ↓
background worker берёт job
        ↓
job.status = running
        ↓
prompt builder собирает messages
        ↓
model_adapter.complete(...)
        ↓
job.status = completed / failed
```

Адаптер отвечает только за один вызов модели.

---

## 14. Интеграция с prompt builder

Model adapter получает уже готовый список сообщений.

Он не должен знать:

- что такое статья;
- что такое лид;
- что такое тон;
- что такое композиция;
- что такое пользовательский лимит символов;
- что такое версия статьи.

Все эти понятия относятся к prompt builder и generation service.

Правильно:

```python
messages = prompt_builder.build_initial_generation_messages(...)
response = await model_adapter.complete(ModelRequest(messages=messages))
```

Неправильно:

```python
response = await model_adapter.generate_article(source_material, tone, length)
```

---

## 15. Формат messages

Для первичной генерации:

```python
messages = [
    ModelMessage(role="system", content=system_prompt),
    ModelMessage(role="user", content=user_prompt),
]
```

Для доработки статьи:

```python
messages = [
    ModelMessage(role="system", content=system_prompt),
    ModelMessage(role="user", content=revision_prompt),
]
```

Не нужно отправлять всю историю чата целиком, если prompt builder уже подставляет:

- последнюю версию статьи;
- исходный материал диалога;
- контекст;
- текущую просьбу пользователя.

Это снижает расход контекста и уменьшает риск того, что модель начнёт учитывать старые, уже неактуальные версии статьи.

---

## 16. Последняя версия статьи

При доработке статьи модель должна получать только последнюю сохранённую версию статьи как основной редактируемый материал.

UI должен показывать пользователю подсказку:

```text
ИИ помнит и редактирует только последнюю версию статьи в этом диалоге.
```

Model adapter не отвечает за выбор версии. Он получает уже собранный prompt.

---

## 17. Логирование технических данных

После каждого вызова модели нужно сохранить технический лог.

Рекомендуемые поля:

- `user_id`;
- `chat_id`;
- `generation_job_id`;
- `model_provider`;
- `model_name`;
- `input_chars`;
- `requested_length_min`;
- `requested_length_max`;
- `max_tokens`;
- `temperature`;
- `top_p`;
- `duration_ms`;
- `status`;
- `error_message`;
- `created_at`.

Запрещено писать в технический лог:

- API key;
- session cookie;
- password hash;
- сырые секреты из `.env`.

Полный prompt можно хранить для admin debug, если это предусмотрено БД. Он должен быть доступен только администратору.

---

## 18. Debug prompt

Для администратора нужно сохранять:

- system prompt;
- user prompt;
- model name;
- параметры генерации;
- ID пользователя;
- ID диалога;
- ID job;
- время запроса;
- статус ответа.

Обычный пользователь не должен видеть debug prompt.

Если в исходном материале пользователя есть конфиденциальная информация, администратор всё равно может её видеть, потому что заказчик подтвердил: админ должен видеть все диалоги пользователей.

---

## 19. Пользовательские ошибки

Model adapter должен отдавать наверх технические исключения, а UI должен показывать безопасные пользовательские сообщения.

Примеры:

### 19.1. Модель недоступна

Пользовательское сообщение:

```text
Не удалось получить ответ от модели. Исходный материал и настройки сохранены. Попробуйте повторить генерацию.
```

Технический лог:

```text
ConnectionError: ...
```

### 19.2. Истёк таймаут

Пользовательское сообщение:

```text
Модель не ответила за отведённое время. Попробуйте повторить генерацию позже.
```

Технический лог:

```text
TimeoutException: ...
```

### 19.3. Неверный API key

Пользовательское сообщение:

```text
Сервис генерации временно недоступен. Обратитесь к администратору.
```

Технический лог для админа:

```text
Authentication error while calling model API.
```

Не показывать обычному пользователю, что именно сломан API key.

### 19.4. Слишком большой контекст

Пользовательское сообщение:

```text
Материал слишком большой для обработки. Сократите текст или обратитесь к администратору для изменения лимита.
```

---

## 20. Нормализация ответа модели

После получения ответа нужно:

1. взять `response.choices[0].message.content`;
2. привести к строке;
3. сделать `.strip()`;
4. проверить, что строка не пустая;
5. сохранить сырой markdown как сообщение ассистента;
6. сохранить эту же версию как новую `article_versions`, если это первичная генерация или успешная доработка.

Не нужно в MVP строго парсить Markdown на отдельные поля `titles`, `lead`, `body`, `questions`.

Но если Codex реализует лёгкий парсер для удобного отображения — это допустимо, при условии что сырой ответ модели всё равно сохраняется.

---

## 21. Проверка структуры ответа

Модель должна возвращать Markdown со структурой:

```markdown
## Варианты заголовков

## Лид

## Статья

## Вопросы к пользователю
```

Backend может проверить наличие ключевых заголовков.

Если структура нарушена:

- не падать с ошибкой 500;
- сохранить сырой ответ;
- показать его пользователю;
- записать warning в technical log;
- при необходимости пометить job как `completed_with_warnings`.

Допустимые статусы job:

```text
queued
running
completed
completed_with_warnings
failed
cancelled
```

---

## 22. Настройки генерации в MVP

Пользователь не управляет техническими параметрами модели.

Пользователь выбирает только:

- тон;
- длину;
- композицию;
- количество абзацев;
- опциональный контекст;
- исходный материал.

Технические параметры:

- `temperature`;
- `top_p`;
- `max_tokens`;
- `model_name`;
- `base_url`;
- `timeout`;

задаются через `.env` или админку, если Codex реализует такую настройку в рамках админ-панели.

---

## 23. Рекомендуемые значения для новостного редактора

```env
MODEL_MAX_TOKENS=2500
MODEL_TEMPERATURE=0.4
MODEL_TOP_P=0.8
MODEL_TIMEOUT_SECONDS=180
MODEL_MAX_RETRIES=1
```

Причина низкой температуры:

- проект требует точности;
- модель не должна выдумывать факты;
- новостной стиль должен быть устойчивым и предсказуемым.

---

## 24. Совместимость с Qwen

В текущем проекте модель указана как:

```text
Qwen/Qwen3-32B
```

При этом заказчик ранее предполагал Qwen 2.5 27B, но фактический пример подключения использует `Qwen/Qwen3-32B`.

Решение для MVP:

- не хардкодить имя модели;
- значение по умолчанию в `.env.example` можно поставить `Qwen/Qwen3-32B`;
- реальное имя модели берётся из `MODEL_NAME`;
- в UI для админа можно показывать текущее имя модели как read-only или editable setting.

---

## 25. `.env.example`

Codex должен создать файл `.env.example`.

Пример:

```env
APP_NAME=AI Article Editor
APP_ENV=development
APP_SECRET_KEY=change-me

DATABASE_URL=sqlite:///./data/app.db

MODEL_PROVIDER=openai_compatible
MODEL_BASE_URL=https://ai.example.com/v1
MODEL_API_KEY=sk-change-me
MODEL_NAME=Qwen/Qwen3-32B
MODEL_TIMEOUT_SECONDS=180
MODEL_MAX_TOKENS=2500
MODEL_TEMPERATURE=0.4
MODEL_TOP_P=0.8
MODEL_MAX_RETRIES=1

MAX_INPUT_CHARS=5000
GENERATION_WORKERS=2
```

---

## 26. Health check модели

Нужен внутренний admin-only endpoint для проверки подключения к модели.

Пример:

```text
POST /admin/model/test
```

Поведение:

- доступ только администратору;
- отправляет короткий тестовый prompt;
- возвращает статус `ok` или `failed`;
- не показывает API key;
- пишет технический результат в лог.

Тестовый prompt:

```text
Ответь одним словом: готов.
```

Ожидается любой непустой ответ.

---

## 27. Пример реализации health check

```python
async def test_model_connection(adapter: OpenAICompatibleModelAdapter) -> dict:
    response = await adapter.complete(
        ModelRequest(
            messages=[
                ModelMessage(role="system", content="Ты отвечаешь кратко."),
                ModelMessage(role="user", content="Ответь одним словом: готов."),
            ],
            max_tokens=20,
            temperature=0.1,
            top_p=0.8,
        )
    )

    return {
        "status": "ok",
        "model_name": response.model_name,
        "duration_ms": response.duration_ms,
        "content_preview": response.content[:200],
    }
```

---

## 28. Работа с OpenAI SDK

В `requirements.txt` добавить:

```text
openai>=1.0.0
```

Если используется Pydantic Settings:

```text
pydantic-settings
```

Если используется FastAPI:

```text
fastapi
uvicorn
```

---

## 29. Нельзя смешивать OpenAI SDK и бизнес-логику

Не должно быть такого кода в route handler:

```python
@app.post("/api/generate")
def generate(...):
    client = OpenAI(...)
    response = client.chat.completions.create(...)
```

Должно быть так:

```python
@app.post("/api/chats/{chat_id}/generate")
async def generate(...):
    job = await generation_service.create_generation_job(...)
    return job
```

А вызов модели происходит внутри generation worker/service через model adapter.

---

## 30. Тестирование model adapter

Нужны тесты двух типов.

### 30.1. Unit-тесты без реальной модели

Использовать mock-клиент.

Проверить:

- адаптер отправляет правильные messages;
- использует `MODEL_NAME`;
- подставляет `max_tokens`, `temperature`, `top_p`;
- возвращает `ModelResponse.content`;
- кидает `ModelAdapterError` при пустом ответе;
- кидает `ModelAdapterError` при исключении клиента;
- не логирует API key.

### 30.2. Интеграционный тест вручную

Команда или admin endpoint:

```text
POST /admin/model/test
```

Проверяет реальное подключение к vLLM.

В автоматический CI этот тест не включать, потому что для него нужен реальный endpoint и секретный ключ.

---

## 31. Mock adapter для тестов

Для тестов и локальной разработки полезно иметь mock adapter.

```python
class MockModelAdapter:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content=(
                "## Варианты заголовков\n\n"
                "1. Тестовый заголовок\n\n"
                "## Лид\n\n"
                "Тестовый лид.\n\n"
                "## Статья\n\n"
                "Тестовая статья.\n\n"
                "## Вопросы к пользователю\n\n"
                "Дополнительные вопросы не требуются."
            ),
            model_name="mock-model",
            duration_ms=1,
        )
```

Можно включать через:

```env
MODEL_PROVIDER=mock
```

Но в MVP обязательна поддержка `openai_compatible`.

---

## 32. Обработка лимитов входного текста

Model adapter не должен сам проверять лимит исходного материала.

Лимит проверяется до сборки промпта:

- ручной текст;
- текст, извлечённый из `.docx`;
- объединённый материал.

Если лимит превышен, запрос к модели не выполняется.

По умолчанию:

```text
MAX_INPUT_CHARS=5000
```

Админ может менять лимит через админку.

---

## 33. Обработка больших ответов

Если модель обрывает ответ из-за `max_tokens`, в `finish_reason` может быть `length`.

Поведение:

- сохранить ответ;
- пометить job как `completed_with_warnings`;
- показать пользователю ответ;
- добавить предупреждение в технический лог;
- в UI можно показать: «Ответ мог быть обрезан моделью. Попробуйте выбрать меньшую длину или повторить генерацию».

---

## 34. Кодировки и русский язык

Все строки должны обрабатываться как UTF-8.

Требования:

- `.env` в UTF-8;
- SQLite в UTF-8;
- HTTP responses в UTF-8;
- TXT export в UTF-8;
- промпты на русском языке;
- модель всегда получает инструкцию отвечать на русском.

---

## 35. Итоговый контракт адаптера

Model adapter считается реализованным, если:

1. параметры модели читаются из конфигурации;
2. используется OpenAI-compatible client;
3. имя модели не захардкожено в бизнес-логике;
4. есть метод `complete(...)`;
5. adapter принимает готовые messages;
6. adapter возвращает нормализованный текст ответа;
7. ошибки модели превращаются в `ModelAdapterError`;
8. таймауты обрабатываются;
9. API key не попадает в логи и ответы;
10. generation service может использовать adapter для первичной генерации и доработки;
11. debug-информация доступна администратору через отдельный механизм;
12. есть unit-тесты с mock-клиентом;
13. есть admin-only health check реального подключения.
