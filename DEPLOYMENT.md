# DEPLOYMENT.md

## 1. Назначение документа

Этот документ описывает развёртывание AI-редактора статей на VPS с Ubuntu 22.x.

Проект разворачивается без Docker:

- Python;
- `venv`;
- FastAPI;
- Uvicorn;
- SQLite;
- systemd;
- Nginx;
- HTTPS через Let's Encrypt;
- OpenAI-compatible API для локальной/внешней Qwen-модели.

Документ предназначен для Codex и должен использоваться при подготовке проекта к production-запуску.

---

## 2. Целевая схема production-развёртывания

Схема:

```text
Internet
   ↓
HTTPS
   ↓
Nginx
   ↓ proxy_pass
127.0.0.1:8000
   ↓
Uvicorn + FastAPI
   ↓
SQLite database
   ↓
OpenAI-compatible model API / vLLM
```

Приложение не должно слушать внешний IP напрямую.

Uvicorn должен быть доступен только локально:

```text
127.0.0.1:8000
```

Наружу приложение публикует Nginx.

---

## 3. Предполагаемый сервер

ОС:

```text
Ubuntu 22.x
```

Минимальные требования зависят от того, где запущена модель.

Если Qwen/vLLM запущена отдельно, для самого веб-приложения достаточно:

- 1–2 CPU;
- 1–2 GB RAM;
- 10+ GB disk;
- Python 3.10+.

Если модель работает на том же сервере, требования определяются моделью и vLLM, но это выходит за рамки данного документа.

---

## 4. Пользователь Linux для приложения

Рекомендуется создать отдельного системного пользователя.

```bash
sudo adduser --system --group --home /opt/article-editor article-editor
```

Рабочая директория проекта:

```text
/opt/article-editor/app
```

Директории данных:

```text
/opt/article-editor/app/data
/opt/article-editor/app/logs
/opt/article-editor/app/tmp
```

Права:

```bash
sudo chown -R article-editor:article-editor /opt/article-editor
sudo chmod 750 /opt/article-editor
```

---

## 5. Установка системных пакетов

```bash
sudo apt update
sudo apt install -y   python3   python3-venv   python3-pip   nginx   sqlite3   git   curl   ufw
```

Если Python 3.10 уже установлен в Ubuntu 22.x, дополнительная установка не нужна.

Проверка:

```bash
python3 --version
```

---

## 6. Получение кода

Вариант через Git:

```bash
cd /opt/article-editor
sudo -u article-editor git clone <REPO_URL> app
cd /opt/article-editor/app
```

Если код копируется вручную, итоговая структура всё равно должна быть:

```text
/opt/article-editor/app
```

---

## 7. Виртуальное окружение

Создать `venv`:

```bash
cd /opt/article-editor/app
sudo -u article-editor python3 -m venv .venv
```

Установить зависимости:

```bash
sudo -u article-editor .venv/bin/pip install --upgrade pip
sudo -u article-editor .venv/bin/pip install -r requirements.txt
```

Проверка:

```bash
sudo -u article-editor .venv/bin/python --version
sudo -u article-editor .venv/bin/pip list
```

---

## 8. Структура проекта на сервере

Рекомендуемая структура:

```text
/opt/article-editor/app/
  app/
    main.py
    core/
    models/
    routers/
    services/
    templates/
    static/
  data/
    app.db
  logs/
    app.log
    error.log
  tmp/
  alembic/                  # если используются миграции Alembic
  tests/
  .env
  .env.example
  requirements.txt
  README.md
```

Директории `data`, `logs`, `tmp` не должны быть доступны как static files.

---

## 9. Переменные окружения

Создать файл:

```bash
sudo -u article-editor nano /opt/article-editor/app/.env
```

Пример `.env`:

```env
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=8000
APP_BASE_URL=https://example.com

SESSION_SECRET=replace-with-long-random-secret
DATABASE_URL=sqlite:////opt/article-editor/app/data/app.db

OPENAI_BASE_URL=https://ai...
OPENAI_API_KEY=sk-...
OPENAI_MODEL=Qwen/Qwen3-32B

MODEL_TIMEOUT_SECONDS=180
MODEL_TEMPERATURE=0.4
MODEL_TOP_P=0.8
MODEL_MAX_TOKENS=2500

MAX_INPUT_CHARS=5000
MAX_UPLOAD_SIZE_MB=5
MAX_CONCURRENT_GENERATIONS=2

SECURE_COOKIES=true
```

Важно:

- `.env` не должен попадать в git;
- API-ключ модели нельзя логировать;
- `SESSION_SECRET` должен быть длинной случайной строкой;
- `DATABASE_URL` для SQLite лучше указывать абсолютным путём.

Сгенерировать секрет можно так:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Права на `.env`:

```bash
sudo chown article-editor:article-editor /opt/article-editor/app/.env
sudo chmod 600 /opt/article-editor/app/.env
```

---

## 10. Создание директорий данных

```bash
sudo -u article-editor mkdir -p /opt/article-editor/app/data
sudo -u article-editor mkdir -p /opt/article-editor/app/logs
sudo -u article-editor mkdir -p /opt/article-editor/app/tmp
```

Права:

```bash
sudo chmod 700 /opt/article-editor/app/data
sudo chmod 700 /opt/article-editor/app/tmp
sudo chmod 750 /opt/article-editor/app/logs
```

---

## 11. Инициализация базы данных

Codex должен предусмотреть команду инициализации БД.

Рекомендуемый вариант:

```bash
sudo -u article-editor /opt/article-editor/app/.venv/bin/python -m app.cli init-db
```

Если используется Alembic:

```bash
sudo -u article-editor /opt/article-editor/app/.venv/bin/alembic upgrade head
```

После инициализации проверить наличие файла:

```bash
ls -lah /opt/article-editor/app/data
```

Права на SQLite:

```bash
sudo chown article-editor:article-editor /opt/article-editor/app/data/app.db
sudo chmod 600 /opt/article-editor/app/data/app.db
```

---

## 12. Создание первого администратора

Свободной регистрации нет. Первого администратора нужно создать CLI-командой.

Codex должен реализовать команду:

```bash
sudo -u article-editor /opt/article-editor/app/.venv/bin/python -m app.cli create-admin
```

Или с параметрами:

```bash
sudo -u article-editor /opt/article-editor/app/.venv/bin/python -m app.cli create-admin   --username admin
```

Команда должна:

1. запросить пароль без отображения в терминале;
2. создать пользователя с ролью `admin`;
3. сохранить пароль только как hash;
4. запретить создание второго пользователя с тем же логином.

Пример интерактивного поведения:

```text
Username: admin
Password:
Repeat password:
Admin user created.
```

---

## 13. Проверка локального запуска

Перед systemd проверить запуск вручную:

```bash
cd /opt/article-editor/app
sudo -u article-editor .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале:

```bash
curl -I http://127.0.0.1:8000
```

Ожидаемо:

```text
HTTP/1.1 200 OK
```

или redirect на страницу входа.

Остановить процесс:

```text
Ctrl+C
```

---

## 14. systemd service

Создать unit-файл:

```bash
sudo nano /etc/systemd/system/article-editor.service
```

Содержимое:

```ini
[Unit]
Description=AI Article Editor FastAPI app
After=network.target

[Service]
Type=simple
User=article-editor
Group=article-editor
WorkingDirectory=/opt/article-editor/app
EnvironmentFile=/opt/article-editor/app/.env
ExecStart=/opt/article-editor/app/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

# Basic hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Применить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable article-editor
sudo systemctl start article-editor
```

Проверить статус:

```bash
sudo systemctl status article-editor
```

Логи:

```bash
journalctl -u article-editor -f
```

---

## 15. Nginx

Создать конфиг:

```bash
sudo nano /etc/nginx/sites-available/article-editor
```

Пример для HTTP до подключения HTTPS:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    client_max_body_size 5M;

    location /static/ {
        alias /opt/article-editor/app/app/static/;
        access_log off;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 240s;
        proxy_connect_timeout 30s;
        proxy_send_timeout 240s;
    }
}
```

Активировать:

```bash
sudo ln -s /etc/nginx/sites-available/article-editor /etc/nginx/sites-enabled/article-editor
sudo nginx -t
sudo systemctl reload nginx
```

Если включён default site, его можно отключить:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## 16. HTTPS через Let's Encrypt

Установить certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Получить сертификат:

```bash
sudo certbot --nginx -d example.com -d www.example.com
```

Проверить автообновление:

```bash
sudo certbot renew --dry-run
```

После HTTPS в `.env` должно быть:

```env
APP_BASE_URL=https://example.com
SECURE_COOKIES=true
```

Перезапустить приложение:

```bash
sudo systemctl restart article-editor
```

---

## 17. Рекомендуемые security headers Nginx

После подключения HTTPS добавить в server block:

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "same-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
```

Базовый CSP, если не ломает frontend:

```nginx
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self';" always;
```

Если используются inline-скрипты, CSP нужно адаптировать.

---

## 18. Firewall

Включить UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Не открывать порт `8000` наружу.

Проверить:

```bash
sudo ss -tulpn
```

Uvicorn должен слушать:

```text
127.0.0.1:8000
```

а не:

```text
0.0.0.0:8000
```

---

## 19. Настройки загрузки `.docx`

Nginx:

```nginx
client_max_body_size 5M;
```

Backend:

```env
MAX_UPLOAD_SIZE_MB=5
```

Файлы `.docx` должны:

1. приниматься только как временные файлы;
2. обрабатываться backend;
3. удаляться после извлечения текста;
4. не сохраняться в static-директории;
5. не быть доступны по URL.

---

## 20. Проверка подключения к модели

В админке должна быть кнопка:

```text
Проверить подключение к модели
```

Также полезно иметь CLI-команду:

```bash
sudo -u article-editor /opt/article-editor/app/.venv/bin/python -m app.cli test-model
```

Команда должна отправить короткий запрос:

```text
Ответь одним словом: OK
```

И вывести:

```text
Model OK. Duration: 1234 ms.
```

При ошибке:

```text
Model error: connection timeout
```

Без вывода API-ключа.

---

## 21. Проверка после деплоя

После запуска проверить:

### 21.1. Сервис

```bash
sudo systemctl status article-editor
curl -I http://127.0.0.1:8000
```

### 21.2. Nginx

```bash
sudo nginx -t
curl -I https://example.com
```

### 21.3. Login

1. открыть `https://example.com`;
2. войти как admin;
3. создать обычного пользователя;
4. выйти;
5. войти как обычный пользователь.

### 21.4. Генерация

1. создать диалог;
2. вставить исходный материал;
3. выбрать параметры;
4. запустить генерацию;
5. дождаться ответа;
6. скачать TXT.

### 21.5. Админка

1. открыть `/admin`;
2. проверить список пользователей;
3. проверить список диалогов;
4. проверить настройки;
5. открыть debug последней генерации;
6. убедиться, что API-ключ не отображается.

### 21.6. Безопасность

Проверить:

- обычный пользователь не открывает `/admin`;
- обычный пользователь не открывает чужой диалог;
- `.env` недоступен по URL;
- `data/app.db` недоступен по URL;
- stack trace не показывается пользователю;
- cookie имеет `HttpOnly`;
- в production cookie имеет `Secure`.

---

## 22. Логи

### 22.1. systemd logs

```bash
journalctl -u article-editor -n 100
journalctl -u article-editor -f
```

### 22.2. Nginx logs

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 22.3. App logs

Если приложение пишет в файлы:

```bash
tail -f /opt/article-editor/app/logs/app.log
tail -f /opt/article-editor/app/logs/error.log
```

Логи не должны содержать:

- пароли;
- API-ключ модели;
- session cookies;
- full Authorization headers.

---

## 23. Бэкап SQLite

SQLite-база хранит пользователей, диалоги, сообщения, версии статей, настройки и технические логи. Нужны регулярные бэкапы.

### 23.1. Директория бэкапов

```bash
sudo mkdir -p /opt/article-editor/backups
sudo chown article-editor:article-editor /opt/article-editor/backups
sudo chmod 700 /opt/article-editor/backups
```

### 23.2. Скрипт бэкапа

Создать файл:

```bash
sudo nano /opt/article-editor/backup.sh
```

Содержимое:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/article-editor/app"
BACKUP_DIR="/opt/article-editor/backups"
DB_PATH="$APP_DIR/data/app.db"
DATE="$(date +%Y-%m-%d_%H-%M-%S)"
BACKUP_PATH="$BACKUP_DIR/app_$DATE.db"

mkdir -p "$BACKUP_DIR"

sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"

gzip "$BACKUP_PATH"

find "$BACKUP_DIR" -name "app_*.db.gz" -type f -mtime +14 -delete

echo "Backup created: $BACKUP_PATH.gz"
```

Права:

```bash
sudo chown article-editor:article-editor /opt/article-editor/backup.sh
sudo chmod 750 /opt/article-editor/backup.sh
```

Проверка:

```bash
sudo -u article-editor /opt/article-editor/backup.sh
```

### 23.3. Cron

Открыть crontab пользователя приложения:

```bash
sudo -u article-editor crontab -e
```

Добавить ежедневный бэкап:

```cron
15 3 * * * /opt/article-editor/backup.sh >> /opt/article-editor/app/logs/backup.log 2>&1
```

---

## 24. Восстановление из бэкапа

Остановить сервис:

```bash
sudo systemctl stop article-editor
```

Сделать копию текущей базы:

```bash
sudo -u article-editor cp /opt/article-editor/app/data/app.db /opt/article-editor/app/data/app.db.before_restore
```

Распаковать нужный бэкап:

```bash
sudo -u article-editor gunzip -c /opt/article-editor/backups/app_YYYY-MM-DD_HH-MM-SS.db.gz > /opt/article-editor/app/data/app.db
```

Права:

```bash
sudo chown article-editor:article-editor /opt/article-editor/app/data/app.db
sudo chmod 600 /opt/article-editor/app/data/app.db
```

Запустить сервис:

```bash
sudo systemctl start article-editor
sudo systemctl status article-editor
```

---

## 25. Обновление приложения

Типовой порядок обновления:

```bash
cd /opt/article-editor/app
sudo -u article-editor git pull
sudo -u article-editor .venv/bin/pip install -r requirements.txt
```

Если есть миграции:

```bash
sudo -u article-editor .venv/bin/alembic upgrade head
```

Если используется собственная CLI-команда:

```bash
sudo -u article-editor .venv/bin/python -m app.cli migrate
```

Перезапуск:

```bash
sudo systemctl restart article-editor
sudo systemctl status article-editor
```

Проверка логов:

```bash
journalctl -u article-editor -n 100
```

---

## 26. Rollback

Перед обновлением рекомендуется сделать бэкап:

```bash
sudo -u article-editor /opt/article-editor/backup.sh
```

Если обновление сломало приложение:

```bash
cd /opt/article-editor/app
sudo -u article-editor git log --oneline -n 5
sudo -u article-editor git checkout <previous_commit>
sudo -u article-editor .venv/bin/pip install -r requirements.txt
sudo systemctl restart article-editor
```

Если миграции уже изменили БД, может потребоваться восстановление из бэкапа.

---

## 27. systemd hardening, дополнительный вариант

После базового запуска можно усилить unit-файл.

Осторожно: некоторые ограничения могут мешать записи в `data/`, `logs/`, `tmp/`.

Пример:

```ini
ProtectSystem=full
ReadWritePaths=/opt/article-editor/app/data /opt/article-editor/app/logs /opt/article-editor/app/tmp
PrivateTmp=true
NoNewPrivileges=true
```

После изменения:

```bash
sudo systemctl daemon-reload
sudo systemctl restart article-editor
```

---

## 28. Производительность и очередь генерации

Ожидаемая нагрузка:

```text
до 30 пользователей
```

Но генерация через LLM тяжёлая, поэтому в приложении должен быть лимит:

```env
MAX_CONCURRENT_GENERATIONS=2
```

Рекомендации:

- не запускать слишком много Uvicorn workers, если очередь реализована внутри процесса;
- для MVP лучше 1 worker, чтобы не усложнять синхронизацию очереди на SQLite;
- если позже потребуется масштабирование, вынести очередь в Redis/Celery/RQ.

Рекомендуемый запуск MVP:

```text
1 Uvicorn process
1 worker
SQLite
internal generation queue
```

---

## 29. Uvicorn workers

Для MVP с SQLite и внутренней очередью использовать один worker.

В systemd:

```ini
ExecStart=/opt/article-editor/app/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Не использовать:

```bash
--workers 4
```

пока очередь генерации не вынесена во внешнее хранилище.

---

## 30. Таймауты

Настройки должны быть согласованы:

Backend:

```env
MODEL_TIMEOUT_SECONDS=180
```

Nginx:

```nginx
proxy_read_timeout 240s;
proxy_send_timeout 240s;
```

Если backend polling-режим не держит длинный HTTP-запрос, Nginx timeout менее критичен, но всё равно должен быть разумным.

---

## 31. Healthcheck

Codex должен реализовать простой endpoint:

```text
GET /health
```

Ответ:

```json
{
  "status": "ok"
}
```

Этот endpoint не должен раскрывать секреты.

Дополнительно можно сделать admin-only endpoint:

```text
GET /admin/health
```

Он может показывать:

- DB status;
- model base URL без API key;
- очередь;
- последнюю ошибку модели.

---

## 32. Static files

Static files должны раздаваться из:

```text
/opt/article-editor/app/app/static/
```

Там могут быть:

- CSS;
- JS;
- favicon;
- изображения интерфейса.

Нельзя размещать в static:

- `.env`;
- SQLite;
- `.docx`;
- бэкапы;
- логи;
- debug prompt files.

---

## 33. Миграции базы

Для MVP допустимо два варианта:

### Вариант 1. Alembic

Предпочтительно, если используется SQLAlchemy.

Команды:

```bash
alembic revision --autogenerate -m "..."
alembic upgrade head
```

### Вариант 2. Собственная init/migrate команда

Если проект проще, можно реализовать:

```bash
python -m app.cli init-db
python -m app.cli migrate
```

Требование:

- схема БД должна воспроизводимо создаваться с нуля;
- обновления схемы не должны терять данные;
- перед миграцией production-БД нужно делать бэкап.

---

## 34. `.env.example`

В репозитории должен быть `.env.example`.

Пример:

```env
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
APP_BASE_URL=http://127.0.0.1:8000

SESSION_SECRET=change-me

DATABASE_URL=sqlite:///./data/app.db

OPENAI_BASE_URL=https://ai.example.com/v1
OPENAI_API_KEY=sk-change-me
OPENAI_MODEL=Qwen/Qwen3-32B

MODEL_TIMEOUT_SECONDS=180
MODEL_TEMPERATURE=0.4
MODEL_TOP_P=0.8
MODEL_MAX_TOKENS=2500

MAX_INPUT_CHARS=5000
MAX_UPLOAD_SIZE_MB=5
MAX_CONCURRENT_GENERATIONS=2

SECURE_COOKIES=false
```

`.env.example` не должен содержать реальные секреты.

---

## 35. `.gitignore`

Минимальный `.gitignore`:

```gitignore
.env
*.env
.venv/
__pycache__/
*.pyc

data/*.db
data/*.sqlite
data/*.sqlite3

logs/*.log
tmp/
uploads/

.pytest_cache/
.coverage
htmlcov/
```

---

## 36. Команды, которые должен предусмотреть проект

Codex должен сделать или описать команды:

```bash
# Установка
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Инициализация
.venv/bin/python -m app.cli init-db

# Создание администратора
.venv/bin/python -m app.cli create-admin

# Проверка модели
.venv/bin/python -m app.cli test-model

# Локальный запуск
.venv/bin/uvicorn app.main:app --reload

# Production-like запуск
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Тесты
.venv/bin/pytest
```

---

## 37. Troubleshooting

### 37.1. Приложение не запускается

Проверить:

```bash
sudo systemctl status article-editor
journalctl -u article-editor -n 100
```

Частые причины:

- не установлен dependency;
- ошибка в `.env`;
- неверный путь к `app.main:app`;
- нет прав на `data/` или `logs/`;
- порт уже занят.

### 37.2. 502 Bad Gateway в Nginx

Проверить:

```bash
sudo systemctl status article-editor
curl -I http://127.0.0.1:8000
sudo tail -n 100 /var/log/nginx/error.log
```

Причины:

- backend не запущен;
- backend слушает другой порт;
- Nginx proxy_pass указывает не туда;
- приложение упало при старте.

### 37.3. Не работает загрузка `.docx`

Проверить:

- `client_max_body_size` в Nginx;
- `MAX_UPLOAD_SIZE_MB`;
- права на `tmp/`;
- установлен ли `python-docx`;
- удаляется ли временный файл после ошибки.

### 37.4. Модель не отвечает

Проверить:

- `OPENAI_BASE_URL`;
- `OPENAI_API_KEY`;
- `OPENAI_MODEL`;
- доступность vLLM endpoint с сервера;
- timeout;
- логи приложения;
- кнопку теста модели в админке.

### 37.5. Пользователь не может войти

Проверить:

- существует ли пользователь;
- активен ли пользователь;
- верный ли пароль;
- корректно ли работает password hash;
- не сработал ли rate limit;
- корректен ли `SESSION_SECRET`.

### 37.6. Cookie не сохраняется

Проверить:

- HTTPS включён;
- `SECURE_COOKIES=true` только в production с HTTPS;
- `SameSite` не мешает сценарию;
- домен в браузере совпадает с доменом приложения.

---

## 38. Production checklist

Перед запуском проверить:

- [ ] создан Linux-пользователь `article-editor`;
- [ ] код лежит в `/opt/article-editor/app`;
- [ ] создан `.env`;
- [ ] реальные секреты не попали в git;
- [ ] установлен `venv`;
- [ ] установлены зависимости;
- [ ] создана SQLite-база;
- [ ] создан первый admin;
- [ ] Uvicorn запускается локально;
- [ ] systemd service работает;
- [ ] Nginx проксирует запросы;
- [ ] HTTPS включён;
- [ ] Uvicorn не открыт наружу;
- [ ] firewall открыт только для SSH и Nginx;
- [ ] `.env` недоступен по URL;
- [ ] `data/app.db` недоступен по URL;
- [ ] `.docx` удаляется после обработки;
- [ ] API-ключ модели не отображается в UI;
- [ ] пользователь не видит чужие диалоги;
- [ ] обычный пользователь не открывает `/admin`;
- [ ] админ видит debug-промпты;
- [ ] настроены бэкапы SQLite;
- [ ] тест подключения к модели успешен;
- [ ] пройдены manual acceptance tests из `TEST_PLAN.md`.

---

## 39. Что не требуется в MVP

В MVP не требуется:

- Docker;
- Kubernetes;
- PostgreSQL;
- Redis;
- Celery;
- S3-хранилище;
- CDN;
- много worker-процессов;
- автоматическое горизонтальное масштабирование;
- сложный мониторинг Prometheus/Grafana;
- zero-downtime deploy.

Эти решения можно добавить позже, если нагрузка вырастет.
