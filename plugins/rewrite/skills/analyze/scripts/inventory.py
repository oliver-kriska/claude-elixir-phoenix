#!/usr/bin/env python3
"""Deterministic, read-only inventory of a legacy application before an Elixir rewrite.

Detects the source stack(s), parses dependency manifests, flags infrastructure
signals (Redis, job queues, realtime, search, ...), locates entry points by
category, samples mechanism hints and "why" comments, lists agent-steering
files, and mines git history for churn hotspots and co-change pairs.

It never writes inside SOURCE and never executes project code. Output is JSON
(for agents) plus a short Markdown summary (for humans).

Every list that is capped reports discovered vs returned counts under
"coverage", so a reader can tell a sample from a census. Regex hints are
leads, not proof that a mechanism is absent.

Usage:
    python3 inventory.py SOURCE [--target DIR] [--steering DIR ...] [--json OUT.json] [--md OUT.md]
                         [--max-commits 2000] [--compare PREV.json]
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter, defaultdict
from itertools import combinations

try:
    import tomllib
except ImportError:  # Python < 3.11: TOML manifests fall back to regex and are reported unparsed
    tomllib = None

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "tmp", "log", "logs", "_build", "deps",
    "dist", "build", "target", "bin", "obj", ".venv", "venv", "env",
    "__pycache__", "coverage", ".next", ".nuxt", ".svelte-kit", ".turbo",
    ".cache", ".idea", ".vscode", "storage", ".bundle", "packs", "assets-cache",
}
SKIP_REL_PREFIXES = ("public/assets", "public/packs", "public/build", "priv/static")
MAX_SCAN_BYTES = 512 * 1024

LANG_BY_EXT = {
    ".rb": "ruby", ".erb": "erb", ".haml": "haml", ".slim": "slim",
    ".py": "python", ".php": "php", ".blade.php": "blade",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".vue": "vue", ".svelte": "svelte",
    ".go": "go", ".java": "java", ".kt": "kotlin", ".scala": "scala",
    ".cs": "csharp", ".fs": "fsharp", ".ex": "elixir", ".exs": "elixir", ".heex": "heex",
    ".rs": "rust", ".sql": "sql", ".html": "html", ".css": "css", ".scss": "css",
    ".pl": "perl", ".pm": "perl", ".cfm": "coldfusion", ".cfc": "coldfusion", ".erl": "erlang",
    ".swift": "swift", ".dart": "dart", ".lua": "lua", ".c": "c", ".cpp": "cpp", ".vb": "vb",
}
SOURCE_LANGS = {
    "ruby", "python", "php", "javascript", "typescript", "go", "java", "kotlin",
    "scala", "csharp", "fsharp", "elixir", "rust", "vue", "svelte",
}

# signal -> (category, dependency-name patterns (lowercase, fnmatch))
SIGNALS = {
    "redis": ("datastore", ["redis", "redis-*", "hiredis", "kredis", "ioredis", "predis/*",
                            "go-redis", "github.com/redis/*", "github.com/go-redis/*", "jedis",
                            "lettuce-core", "spring-boot-starter-data-redis", "django-redis",
                            "channels_redis", "stackexchange.redis"]),
    "memcached": ("cache", ["dalli", "memcached", "pymemcache", "python-memcached", "memjs"]),
    "sidekiq": ("jobs", ["sidekiq", "sidekiq-*"]),
    "resque": ("jobs", ["resque", "resque-*"]),
    "delayed_job": ("jobs", ["delayed_job", "delayed_job_*"]),
    "good_job/solid_queue/que": ("jobs", ["good_job", "solid_queue", "que"]),
    "celery": ("jobs", ["celery", "django-celery-*"]),
    "rq/dramatiq/huey": ("jobs", ["rq", "django-rq", "dramatiq", "huey"]),
    "bull/bullmq/agenda": ("jobs", ["bull", "bullmq", "agenda", "bee-queue", "@nestjs/bull*", "pg-boss"]),
    "laravel-horizon": ("jobs", ["laravel/horizon"]),
    "hangfire": ("jobs", ["hangfire*"]),
    "quartz": ("jobs", ["quartz", "spring-boot-starter-quartz"]),
    "asynq/machinery": ("jobs", ["github.com/hibiken/asynq", "github.com/richardknop/machinery*"]),
    "cron": ("scheduling", ["whenever", "sidekiq-cron", "sidekiq-scheduler", "rufus-scheduler",
                            "django-celery-beat", "node-cron", "cron", "@nestjs/schedule",
                            "github.com/robfig/cron*", "apscheduler", "solid_queue"]),
    "actioncable/anycable": ("realtime", ["actioncable", "anycable*", "@rails/actioncable"]),
    "turbo/hotwire": ("ui", ["turbo-rails", "stimulus-rails", "@hotwired/turbo*", "@hotwired/stimulus"]),
    "django-channels": ("realtime", ["channels", "daphne"]),
    "socket.io/ws": ("realtime", ["socket.io", "socket.io-client", "ws", "@nestjs/websockets",
                                  "@nestjs/platform-socket.io", "github.com/gorilla/websocket",
                                  "nhooyr.io/websocket", "github.com/coder/websocket"]),
    "pusher/reverb/echo": ("realtime", ["pusher", "pusher/*", "laravel-echo", "laravel/reverb",
                                        "pusher-js"]),
    "signalr": ("realtime", ["microsoft.aspnetcore.signalr*", "@microsoft/signalr"]),
    "kafka": ("messaging", ["ruby-kafka", "karafka", "rdkafka", "kafkajs", "confluent-kafka",
                            "kafka-python", "github.com/shopify/sarama", "github.com/ibm/sarama",
                            "github.com/segmentio/kafka-go", "spring-kafka", "confluent.kafka"]),
    "rabbitmq": ("messaging", ["bunny", "sneakers", "amqplib", "pika", "php-amqplib/*",
                               "github.com/rabbitmq/amqp091-go", "spring-boot-starter-amqp",
                               "rabbitmq.client", "masstransit*"]),
    "sqs/sns": ("messaging", ["aws-sdk-sqs", "@aws-sdk/client-sqs", "shoryuken"]),
    "elasticsearch/opensearch": ("search", ["elasticsearch*", "searchkick", "chewy",
                                            "@elastic/elasticsearch", "opensearch*",
                                            "django-elasticsearch-dsl"]),
    "meilisearch/typesense/algolia": ("search", ["meilisearch*", "typesense*", "algolia*",
                                                 "algoliasearch*", "laravel/scout"]),
    "pg_search/ransack": ("search", ["pg_search", "ransack"]),
    "file-storage": ("storage", ["activestorage", "aws-sdk-s3", "@aws-sdk/client-s3", "shrine",
                                 "carrierwave", "paperclip", "django-storages", "boto3",
                                 "multer", "league/flysystem*", "awssdk.s3"]),
    "image-processing": ("media", ["image_processing", "mini_magick", "ruby-vips", "sharp",
                                   "pillow", "jimp", "intervention/image", "imagesharp*"]),
    "mail": ("mail", ["actionmailer", "mail", "postmark*", "sendgrid*", "mailgun*", "nodemailer",
                      "@sendgrid/mail", "django-anymail", "symfony/mailer"]),
    "inbound-mail": ("mail", ["actionmailbox", "griddler"]),
    "auth": ("auth", ["devise", "omniauth*", "rodauth*", "sorcery", "clearance", "bcrypt",
                      "bcryptjs", "express-jwt", "argon2", "@node-rs/bcrypt", "@node-rs/argon2",
                      "django-allauth", "djangorestframework-simplejwt", "passport", "passport-*",
                      "next-auth", "@auth/*", "jsonwebtoken", "jose", "laravel/sanctum",
                      "laravel/passport", "laravel/fortify", "laravel/breeze",
                      "spring-boot-starter-security", "github.com/golang-jwt/jwt*",
                      "microsoft.aspnetcore.identity*"]),
    "authorization": ("auth", ["pundit", "cancancan", "action_policy", "django-guardian",
                               "rules", "@casl/*", "casbin", "spatie/laravel-permission"]),
    "payments": ("integration", ["stripe", "stripe-*", "@stripe/*", "braintree", "paddle*",
                                 "laravel/cashier*", "pay"]),
    "graphql": ("api", ["graphql", "graphql-ruby", "graphene*", "strawberry-graphql",
                        "@apollo/server", "apollo-server*", "@nestjs/graphql",
                        "github.com/99designs/gqlgen", "hotchocolate*"]),
    "api-serialization": ("api", ["jbuilder", "active_model_serializers", "blueprinter",
                                  "jsonapi-serializer", "djangorestframework", "class-transformer"]),
    "admin": ("admin", ["activeadmin", "administrate", "rails_admin", "avo", "django-jazzmin",
                        "laravel/nova", "filament/filament"]),
    "feature-flags": ("ops", ["flipper*", "launchdarkly*", "unleash*", "django-waffle"]),
    "multi-tenancy": ("data", ["ros-apartment", "apartment", "acts_as_tenant", "django-tenants",
                               "stancl/tenancy"]),
    "state-machines": ("domain", ["aasm", "state_machines*", "django-fsm*", "xstate"]),
    "audit-trail": ("data", ["paper_trail", "audited", "logidze", "django-simple-history",
                             "owen-it/laravel-auditing"]),
    "soft-delete": ("data", ["paranoia", "discard", "django-safedelete"]),
    "rate-limiting": ("security", ["rack-attack", "django-ratelimit", "express-rate-limit",
                                   "rate-limiter-flexible", "@nestjs/throttler"]),
    "i18n": ("ui", ["rails-i18n", "i18n-tasks", "i18next", "react-i18next", "vue-i18n",
                    "django-modeltranslation", "mobility", "globalize"]),
    "web-push": ("integration", ["web-push", "webpush", "pywebpush", "minishlink/web-push",
                                 "rpush", "firebase-admin"]),
    "pdf": ("media", ["prawn", "wicked_pdf", "grover", "weasyprint", "puppeteer", "pdfkit",
                      "barryvdh/laravel-dompdf"]),
    "observability": ("ops", ["sentry*", "@sentry/*", "newrelic*", "ddtrace", "dd-trace",
                              "appsignal", "skylight", "scout_apm", "opentelemetry*",
                              "@opentelemetry/*", "prometheus*", "prom-client"]),
    "orm": ("data", ["activerecord", "sequel", "prisma", "@prisma/client", "typeorm",
                     "sequelize", "drizzle-orm", "mongoose", "knex", "sqlalchemy",
                     "gorm.io/gorm", "github.com/jmoiron/sqlx", "entgo.io/ent",
                     "microsoft.entityframeworkcore*", "spring-boot-starter-data-jpa",
                     "hibernate-core", "doctrine/orm"]),
    "sqlite": ("datastore", ["sqlite3", "better-sqlite3", "sqlite", "github.com/mattn/go-sqlite3",
                             "modernc.org/sqlite", "microsoft.entityframeworkcore.sqlite"]),
    "postgres": ("datastore", ["pg", "psycopg*", "postgres", "pg-promise", "github.com/lib/pq",
                               "github.com/jackc/pgx*", "npgsql*", "org.postgresql:postgresql"]),
    "mysql": ("datastore", ["mysql2", "mysqlclient", "pymysql", "mysql", "mysql2-*",
                            "github.com/go-sql-driver/mysql", "mysql-connector-*"]),
    "mongodb": ("datastore", ["mongoid", "mongoose", "pymongo", "mongodb", "go.mongodb.org/*"]),
    "rich-text": ("ui", ["actiontext", "trix", "@rails/actiontext", "tiptap*", "@tiptap/*",
                         "quill", "prosemirror*", "lexical"]),
    "spa-frontend": ("ui", ["react", "react-dom", "vue", "@angular/core", "svelte", "solid-js",
                            "preact"]),
    "proxy/server": ("ops", ["puma", "unicorn", "passenger", "thruster", "falcon", "gunicorn",
                             "uvicorn", "daphne", "hypercorn", "pm2", "kestrel"]),
    "go-http": ("shape", ["github.com/gin-gonic/gin", "github.com/labstack/echo*", "github.com/go-chi/chi*",
                          "github.com/gofiber/fiber*", "github.com/gorilla/mux"]),
    "cli": ("shape", ["thor", "dry-cli", "click", "typer", "docopt", "commander", "yargs", "oclif",
                      "@oclif/core", "github.com/spf13/cobra", "github.com/urfave/cli*", "clap",
                      "picocli", "symfony/console", "system.commandline"]),
    "data-pipeline": ("shape", ["apache-airflow", "dagster", "prefect", "luigi", "pyspark", "dbt-*",
                                "pandas", "polars", "apache-beam", "spark-core*", "spring-batch*"]),
    "ml-inference": ("shape", ["torch", "tensorflow", "scikit-learn", "transformers", "onnxruntime",
                               "xgboost", "lightgbm", "keras", "jax", "candle-core", "ort"]),
    "desktop": ("shape", ["electron", "tauri", "@tauri-apps/api", "pyqt*", "pyside*", "tkinter",
                          "wails", "fyne.io/fyne*", "javafx*"]),
    "serverless": ("shape", ["serverless", "aws-lambda*", "@aws-cdk/*", "aws-cdk-lib", "chalice",
                             "zappa", "mangum", "github.com/aws/aws-lambda-go"]),
    "async-runtime": ("concurrency", ["tokio", "async-std", "asyncio", "trio", "gevent", "eventlet",
                                      "reactor-core", "kotlinx-coroutines*", "akka-actor*", "pekko-actor*"]),
}

# Language-level stack per primary manifest, reported when no framework marker matches a root.
LANGUAGE_BY_MANIFEST = {
    "Gemfile": "ruby", "package.json": "node", "pyproject.toml": "python", "requirements.txt": "python",
    "Pipfile": "python", "setup.py": "python", "composer.json": "php", "go.mod": "go", "pom.xml": "jvm",
    "build.gradle": "jvm", "build.gradle.kts": "jvm", "build.sbt": "scala", "Cargo.toml": "rust",
    "mix.exs": "elixir", "cpanfile": "perl", "Makefile.PL": "perl", "manage.py": "python",
}

# stack -> list of (marker type, value). "file" = path exists, "dep" = dependency present
STACK_MARKERS = {
    "rails": [("file", "config/routes.rb"), ("dep", "rails"), ("dep", "railties")],
    "sinatra/hanami/roda": [("dep", "sinatra"), ("dep", "hanami"), ("dep", "roda")],
    "django": [("file", "manage.py"), ("dep", "django")],
    "flask/fastapi": [("dep", "flask"), ("dep", "fastapi")],
    "laravel": [("file", "artisan"), ("dep", "laravel/framework")],
    "symfony": [("dep", "symfony/framework-bundle")],
    "express/koa/hapi": [("dep", "express"), ("dep", "koa"), ("dep", "@hapi/hapi")],
    "nestjs": [("dep", "@nestjs/core")],
    "fastify": [("dep", "fastify")],
    "nextjs/remix/nuxt": [("dep", "next"), ("dep", "@remix-run/node"), ("dep", "nuxt")],
    "go": [("file", "go.mod")],
    "spring": [("dep", "spring-boot-starter-web"), ("dep", "spring-boot-starter-webflux"),
               ("dep", "spring-boot-starter")],
    "quarkus/micronaut/ktor": [("dep", "quarkus-*"), ("dep", "micronaut-*"), ("dep", "ktor-server-*")],
    "aspnetcore": [("dep", "microsoft.aspnetcore*")],
    "wordpress": [("file", "wp-config.php"), ("file", "wp-config-sample.php"), ("dep", "johnpbloch/wordpress*")],
    "rust-web (axum/actix/rocket)": [("dep", "axum"), ("dep", "actix-web"), ("dep", "rocket"), ("dep", "warp")],
    "scala (play/akka/pekko)": [("dep", "play*"), ("dep", "akka-*"), ("dep", "pekko-*")],
    "perl (mojolicious/catalyst/dancer)": [("dep", "mojolicious"), ("dep", "catalyst-runtime"), ("dep", "dancer*")],
    "elixir": [("file", "mix.exs")],
}

# Stack pack (relative to the KB) the analysts read for each detected stack.
STACK_PACKS = {
    "rails": "rails", "sinatra/hanami/roda": "rails",
    "django": "django", "flask/fastapi": "django",
    "laravel": "laravel", "symfony": "laravel",
    "express/koa/hapi": "node", "nestjs": "node", "fastify": "node", "nextjs/remix/nuxt": "node",
    "go": "go",
    "spring": "jvm-dotnet", "quarkus/micronaut/ktor": "jvm-dotnet", "aspnetcore": "jvm-dotnet",
    "scala (play/akka/pekko)": "jvm-dotnet",
}


def stack_pack(stack):
    return f"stacks/{STACK_PACKS.get(stack, 'generic')}.md"

# (glob, category). Matched against path relative to SOURCE, first match wins per category list.
ENTRY_GLOBS = [
    ("test/*", "tests"), ("spec/*", "tests"), ("tests/*", "tests"), ("*_test.go", "tests"),
    ("*.test.*", "tests"), ("*.spec.*", "tests"), ("*/__tests__/*", "tests"), ("*Test.java", "tests"),
    ("*Tests.cs", "tests"), ("*/tests/*", "tests"), ("*/test_*.py", "tests"), ("*_test.py", "tests"),
    ("e2e/*", "tests"), ("cypress/*", "tests"), ("playwright*", "tests"),
    ("Dockerfile*", "deployment"), ("docker-compose*", "deployment"), ("compose*.y*ml", "deployment"),
    ("Procfile*", "deployment"), ("fly.toml", "deployment"), ("config/deploy*", "deployment"),
    ("k8s/*", "deployment"), ("helm/*", "deployment"), ("*.service", "deployment"),
    (".github/workflows/*", "ci"), (".gitlab-ci.yml", "ci"), (".circleci/*", "ci"),
    ("db/migrate/*", "migrations"), ("*/migrations/*", "migrations"), ("database/migrations/*", "migrations"),
    ("db/migration/*", "migrations"), ("Migrations/*", "migrations"),
    ("db/schema.rb", "schema"), ("db/structure.sql", "schema"), ("*schema.sql", "schema"),
    ("app/views/*", "views"), ("*/templates/*", "views"), ("resources/views/*", "views"),
    ("app/javascript/*", "frontend"), ("app/assets/javascripts/*", "frontend"),
    ("resources/js/*", "frontend"), ("frontend/*", "frontend"), ("client/*", "frontend"),
    ("src/components/*", "frontend"), ("pages/*", "frontend"), ("app/frontend/*", "frontend"),
    ("config/routes.rb", "routes"), ("config/routes/*.rb", "routes"), ("*urls.py", "routes"),
    ("routes/*.php", "routes"), ("*routes*.ts", "routes"), ("*routes*.js", "routes"),
    ("*router*.go", "routes"), ("*routes*.go", "routes"), ("lib/*_web/router.ex", "routes"),
    ("app/models/concerns/*", "concerns"), ("app/controllers/concerns/*", "concerns"),
    ("app/models/*", "models"), ("*models.py", "models"), ("*/models/*.py", "models"),
    ("app/Models/*", "models"), ("*.entity.ts", "models"), ("*schema.prisma", "models"),
    ("*/models/*.go", "models"), ("*Entity.java", "models"), ("*Entity.kt", "models"),
    ("*DbContext.cs", "models"),
    ("app/controllers/*", "controllers"), ("*views.py", "controllers"), ("*viewsets.py", "controllers"),
    ("app/Http/Controllers/*", "controllers"), ("*.controller.ts", "controllers"),
    ("*controller*.js", "controllers"), ("*handler*.go", "handlers"),
    ("*Controller.java", "controllers"), ("*Controller.kt", "controllers"), ("*Controller.cs", "controllers"),
    ("app/jobs/*", "jobs"), ("app/workers/*", "jobs"), ("app/sidekiq/*", "jobs"), ("*tasks.py", "jobs"),
    ("app/Jobs/*", "jobs"), ("*/workers/*", "jobs"), ("*_worker.rb", "jobs"), ("*_worker.py", "jobs"),
    ("*.worker.ts", "jobs"), ("*worker.go", "jobs"), ("*/queues/*", "jobs"), ("*.processor.ts", "jobs"),
    ("app/channels/*", "realtime"), ("*consumers.py", "realtime"), ("*routing.py", "realtime"),
    ("*.gateway.ts", "realtime"), ("*Hub.cs", "realtime"), ("app/Events/*", "realtime"),
    ("app/mailers/*", "mail"), ("app/mailboxes/*", "mail"), ("app/Mail/*", "mail"),
    ("config/initializers/*", "config"), ("config/*.yml", "config"), ("config/*.rb", "config"),
    ("*settings*.py", "config"), ("config/*.php", "config"), ("*application*.yml", "config"),
    ("*application*.properties", "config"), ("appsettings*.json", "config"), (".env.example", "config"),
    ("app/helpers/*", "helpers"), ("*middleware*", "middleware"),
    ("*signals.py", "callbacks"), ("app/Observers/*", "callbacks"), ("app/Listeners/*", "callbacks"),
    ("config/schedule.rb", "scheduling"), ("app/Console/Kernel.php", "scheduling"),
    ("*celery*.py", "scheduling"), ("config/recurring.yml", "scheduling"), ("config/sidekiq*.yml", "scheduling"),
    ("lib/tasks/*", "tasks"), ("*/management/commands/*", "tasks"), ("app/Console/Commands/*", "tasks"),
    ("lib/*", "lib"),
]

STEERING_GLOBS = [
    "AGENTS.md", "*/AGENTS.md", "CLAUDE.md", "*/CLAUDE.md", ".cursorrules", ".cursor/rules/*",
    ".github/copilot-instructions.md", ".agents/skills/*/SKILL.md", ".claude/skills/*/SKILL.md",
    ".claude/agents/*.md", ".windsurfrules", "migration.toml", "plans/*.md", "plans/*.json",
    "parity/cases.json", "CONVENTIONS.md", "ARCHITECTURE.md", "docs/adr/*", "doc/adr/*",
]

# label -> (languages it applies to, regex)
MECHANISM_HINTS = {
    "model-callbacks": ({"ruby"}, r"\b(after_commit|after_save|before_save|after_create|before_create|"
                                  r"after_update|before_validation|after_destroy|before_destroy|around_\w+)\b"),
    "controller-filters": ({"ruby"}, r"\b(before_action|after_action|around_action|skip_before_action)\b"),
    "async-jobs": ({"ruby", "python", "php", "javascript", "typescript"},
                   r"\b(perform_later|perform_async|deliver_later|\.delay\(|apply_async|dispatch\(|"
                   r"ShouldQueue|queue\.add\(|enqueue)\b"),
    "realtime-broadcast": ({"ruby", "python", "php", "javascript", "typescript", "csharp", "go"},
                           r"(broadcast_\w+|turbo_stream|ActionCable\.server\.broadcast|broadcasts_to|"
                           r"channel_layer|group_send|ShouldBroadcast|io\.(to|emit)|socket\.emit|"
                           r"Clients\.(All|Group))"),
    "caching": ({"ruby", "python", "php", "javascript", "typescript", "java", "kotlin", "csharp", "go"},
                r"(Rails\.cache|\bcache\.(get|set|fetch)|@cache_page|Cache::|@Cacheable|"
                r"IMemoryCache|IDistributedCache|fresh_when|stale\?|\bcache\s+\[?@?\w)"),
    "locks-and-transactions": ({"ruby", "python", "php", "java", "kotlin", "csharp", "go",
                                "javascript", "typescript"},
                               r"(with_lock|lock!|advisory_lock|select_for_update|transaction\.atomic|"
                               r"@Transactional|DB::transaction|\.transaction\s*(do|\()|sync\.(RW)?Mutex|"
                               r"\block\s*\(|synchronized\b|Redlock|redlock)"),
    "request-globals": ({"ruby", "python", "javascript", "typescript"},
                        r"(Current\.\w+|CurrentAttributes|Thread\.current|threading\.local|"
                        r"AsyncLocalStorage|cls-hooked)"),
    "crypto-contracts": ({"ruby", "python", "php", "javascript", "typescript"},
                         r"(MessageVerifier|MessageEncryptor|signed_id|generates_token_for|encrypts\b|"
                         r"signing\.(dumps|loads)|TimestampSigner|cookies\.(signed|encrypted)|"
                         r"Crypt::|jwt\.(sign|verify)|\bbcrypt(?:js)?\.(?:hash|compare)(?:Sync)?\b|"
                         r"\bargon2\.(?:hash|verify)(?:Sync)?\b|has_secure_password|make_password|check_password)"),
    "derived-data": ({"ruby", "python"}, r"(counter_cache|touch:\s*true|default_scope|\benum\s)"),
    "concurrency": ({"ruby", "python", "javascript", "typescript", "go", "java", "kotlin", "csharp"},
                    r"(Thread\.new|Concurrent::|ThreadPoolExecutor|asyncio\.(gather|create_task)|"
                    r"worker_threads|cluster\.fork|new Worker\(|\bgo func\b|\bgo \w+\(|make\(chan|"
                    r"CompletableFuture|ExecutorService|@Async|Task\.Run|BackgroundService|IHostedService)"),
    "timers-and-polling": ({"javascript", "typescript", "go", "ruby", "python"},
                           r"(setInterval\(|time\.NewTicker|time\.Tick\(|sleep\s*\(?\d|"
                           r"every\s+\d+\.(seconds|minutes)|@Scheduled|cron\.schedule)"),
    "metaprogramming": ({"ruby", "python", "javascript", "typescript"},
                        r"(method_missing|define_method|class_eval|instance_eval|send\(:|__getattr__|"
                        r"setattr\(|new Proxy\(|Reflect\.)"),
    "events-and-observers": ({"ruby", "python", "php", "javascript", "typescript", "java", "csharp"},
                             r"(ActiveSupport::Notifications|post_save|pre_save|@receiver|Event::listen|"
                             r"EventEmitter|\.on\(['\"]|@EventListener|INotificationHandler|wisper)"),
    "external-http": ({"ruby", "python", "php", "javascript", "typescript", "go", "java", "csharp"},
                      r"(Net::HTTP|Faraday|HTTParty|requests\.(get|post)|httpx\.|axios\.|fetch\(|"
                      r"Http::(get|post)|http\.(Get|Post|NewRequest)|RestTemplate|WebClient|HttpClient)"),
    "raw-sql": ({"ruby", "python", "php", "javascript", "typescript", "go", "java", "csharp"},
                r"(find_by_sql|execute\(\s*['\"](SELECT|UPDATE|INSERT|DELETE)|\.raw\(|DB::(select|statement)|"
                r"\$queryRaw|db\.(Query|Exec)\(|createNativeQuery|FromSqlRaw)"),
}

WHY_COMMENT_RE = re.compile(
    r"(#|//|/\*|\*|--)\s*.*\b(because|workaround|work around|hack|due to|otherwise|so that|"
    r"to prevent|to avoid|in order to|needed for|required (by|for)|legacy|compat|backward|"
    r"race condition|deadlock|n\+1|perf(ormance)?|cache)\b",
    re.IGNORECASE,
)
FIX_RE = re.compile(r"\b(fix|fixes|fixed|bug|hotfix|revert|regression|crash|broken|patch)\b", re.I)
LOCKFILES = {"Gemfile.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
             "composer.lock", "go.sum", "Pipfile.lock", "mix.lock", "Cargo.lock", "bun.lockb"}


def rel(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def lang_of(name):
    if name.endswith(".blade.php"):
        return "blade"
    return LANG_BY_EXT.get(os.path.splitext(name)[1].lower())


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        r = rel(dirpath, root)
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".git")
            and not (r + "/" + d if r != "." else d).startswith(SKIP_REL_PREFIXES)
        )
        # Report linked directories as skipped entries, never traverse their targets.
        linked = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        dirnames[:] = [d for d in dirnames if d not in linked]
        for d in linked:
            yield os.path.join(dirpath, d)
        for f in sorted(filenames):
            yield os.path.join(dirpath, f)


SPECIAL_TYPES = ((stat.S_ISFIFO, "fifo"), (stat.S_ISSOCK, "socket"),
                 (stat.S_ISCHR, "char-device"), (stat.S_ISBLK, "block-device"))


def special_type(mode):
    """Type name of a file that is not regular, a symlink or a directory; else None."""
    if stat.S_ISREG(mode) or stat.S_ISLNK(mode) or stat.S_ISDIR(mode):
        return None
    return next((name for test, name in SPECIAL_TYPES if test(mode)), "special")


def file_id(st):
    """Metadata that changes when a path is written to or replaced."""
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def open_regular(path, st):
    """Open `path` for reading only while it is still the regular file `st` describes.

    Returns None for any other type: opening a FIFO or device can block forever.
    The final component is never followed, and the descriptor must be the inode
    lstat saw, so a file swapped in between is not mistaken for the scanned one.
    """
    if not stat.S_ISREG(st.st_mode):
        return None
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    fh = os.fdopen(fd, "rb")
    if file_id(os.fstat(fh.fileno())) != file_id(st):
        fh.close()
        return None
    return fh


def read_text(path, limit=MAX_SCAN_BYTES):
    try:
        st = os.lstat(path)
        if st.st_size > limit:
            return None
        fh = open_regular(path, st)
        if fh is None:
            return None
        with fh:
            data = fh.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit or b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def parse_gemfile(text):
    return re.findall(r"^\s*gem\s+['\"]([^'\"]+)['\"]", text, re.M)


def parse_gemfile_lock(text):
    deps, in_specs = [], False
    for line in text.splitlines():
        if line.strip() == "specs:":
            in_specs = True
            continue
        if in_specs and re.match(r"^\S", line):
            in_specs = False
        m = re.match(r"^    ([a-zA-Z0-9_.-]+) \(([^)]+)\)", line) if in_specs else None
        if m:
            deps.append(f"{m.group(1)}@{m.group(2)}")
    return deps


def parse_package_json(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        for name, ver in (data.get(key) or {}).items():
            out.append(f"{name}@{ver}")
    return out


def parse_requirements(text):
    out = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*([<>=!~].*)?$", line)
        if m and not line.startswith("-"):
            out.append(m.group(1).split("[")[0] + ("@" + m.group(2).strip() if m.group(2) else ""))
    return out


class Fallback(list):
    """Dependencies a regex recovered from a manifest the structured parser could not read."""


def parse_pyproject_regex(text):
    out = re.findall(r"^\s*['\"]([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*[<>=~!^]?[^'\"]*['\"]\s*,?\s*$", text, re.M)
    out += re.findall(r"^([A-Za-z0-9_.\-]+)\s*=\s*['\"{]", text, re.M)
    return [x for x in out if x.lower() not in {"python", "name", "version", "description", "readme"}]


def toml_table(node, *keys):
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def requirement(spec):
    """PEP 508 string -> "name" or "name@constraint"."""
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._\-]*)\s*(?:\[[^\]]*\])?\s*(.*)", spec)
    if not m:
        return None
    rest = m.group(2).strip().lstrip("@").strip()
    return m.group(1) + ("@" + rest if rest else "")


def parse_pyproject(text):
    """pyproject.toml (PEP 621/735, Poetry, uv, PDM) and Pipfile dependencies."""
    if tomllib is None:
        return Fallback(parse_pyproject_regex(text))
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return Fallback(parse_pyproject_regex(text))
    project, tool = toml_table(data, "project"), toml_table(data, "tool")
    arrays = [project.get("dependencies"), toml_table(tool, "uv").get("dev-dependencies")]
    for groups in (toml_table(project, "optional-dependencies"), toml_table(data, "dependency-groups"),
                   toml_table(tool, "pdm", "dev-dependencies")):
        arrays += groups.values()
    out = [requirement(s) for a in arrays if isinstance(a, list) for s in a if isinstance(s, str)]
    poetry = toml_table(tool, "poetry")
    tables = [toml_table(poetry, "dependencies"), toml_table(poetry, "dev-dependencies"),
              *(toml_table(group, "dependencies") for group in toml_table(poetry, "group").values()),
              toml_table(data, "packages"), toml_table(data, "dev-packages")]
    for table in tables:
        for name, spec in table.items():
            version = spec.get("version") if isinstance(spec, dict) else spec
            if name.lower() != "python":
                out.append(name + (f"@{version}" if isinstance(version, str) and version else ""))
    return [d for d in out if d]


def parse_composer(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for key in ("require", "require-dev"):
        for name, ver in (data.get(key) or {}).items():
            out.append(f"{name}@{ver}")
    return out


def parse_go_mod(text):
    out = re.findall(r"^\s*(?:require\s+)?([a-zA-Z0-9.\-/]+\.[a-z]{2,}/[^\s]+)\s+(v[^\s]+)", text, re.M)
    return [f"{n}@{v}" for n, v in out]


def parse_maven_gradle(text):
    out = re.findall(r"<artifactId>([^<]+)</artifactId>", text)
    out += re.findall(r"['\"]([a-zA-Z0-9.\-]+):([a-zA-Z0-9.\-]+)(?::[^'\"]+)?['\"]", text)
    flat = []
    for item in out:
        flat.append(item[1] if isinstance(item, tuple) else item)
    return flat


def parse_csproj(text):
    return re.findall(r'PackageReference\s+Include="([^"]+)"', text)


def parse_cargo(text):
    out, section = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.strip("[]")
            continue
        if section.endswith("dependencies"):
            m = re.match(r"^([A-Za-z0-9_\-]+)\s*=", stripped)
            if m:
                out.append(m.group(1))
    return out


def parse_sbt(text):
    return [m[1] for m in re.findall(r'"([^"]+)"\s+%%?%?\s+"([^"]+)"', text)]


def parse_cpanfile(text):
    return [m.lower().replace("::", "-") for m in re.findall(r"^\s*requires\s+['\"]([\w:]+)['\"]", text, re.M)]


def parse_mix(text):
    return re.findall(r"\{:([a-z0-9_]+),", text)


LOCK_MANIFESTS = {"Gemfile.lock"}

# Files whose directory is an application root (monorepos have several).
PRIMARY_MANIFESTS = {
    "Gemfile", "package.json", "pyproject.toml", "requirements.txt", "Pipfile", "setup.py",
    "composer.json", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts", "mix.exs", "manage.py",
    "Cargo.toml", "build.sbt", "cpanfile", "Makefile.PL",
}
# Recognized as manifests but not parsed: reported so "no deps found" is not mistaken for "no deps".
UNPARSED_MANIFESTS = ("setup.py", "setup.cfg", "Package.swift", "*.fsproj", "*.vbproj", "*.sln",
                      "deno.json", "bun.lockb", "packages.config", "pubspec.yaml", "Makefile.PL")
FIXTURE_ROOT_RE = re.compile(r"(^|/)(test|tests|spec|fixtures?|examples?|samples?|e2e)(/|$)")
ENTRY_CAP, WHY_CAP, HINT_TOP = 400, 60, 8

MANIFEST_PARSERS = {
    "Gemfile": parse_gemfile, "Gemfile.lock": parse_gemfile_lock, "package.json": parse_package_json,
    "requirements.txt": parse_requirements,
    "pyproject.toml": parse_pyproject, "Pipfile": parse_pyproject, "composer.json": parse_composer,
    "go.mod": parse_go_mod, "pom.xml": parse_maven_gradle, "build.gradle": parse_maven_gradle,
    "build.gradle.kts": parse_maven_gradle, "mix.exs": parse_mix, "Cargo.toml": parse_cargo,
    "build.sbt": parse_sbt, "cpanfile": parse_cpanfile,
}


def manifest_parser(app_relpath, name):
    if name in MANIFEST_PARSERS:
        return MANIFEST_PARSERS[name]
    if name.endswith(".csproj"):
        return parse_csproj
    if fnmatch.fnmatch(app_relpath, "requirements/*.txt"):
        return parse_requirements
    return None


def dep_name(entry):
    if entry.startswith("@"):
        return "@" + entry[1:].split("@")[0].lower()
    return entry.split("@")[0].lower()


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

# Config a checkout can carry that makes read-only git commands run programs:
# an fsmonitor hook, any hook, signature checks (gpg.program) and the transport
# a partial clone uses to fetch missing objects (core.sshCommand, helpers).
GIT_SAFE_CONFIG = ("core.fsmonitor=false", f"core.hooksPath={os.devnull}", "log.showSignature=false",
                   "protocol.allow=never")


def git(args, cwd, options=()):
    # Inherited GIT_* variables can point git at another repository (GIT_DIR,
    # GIT_WORK_TREE, GIT_INDEX_FILE) or inject config. Optional locks off: a
    # read must not refresh the legacy checkout's index.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k == "GIT_CEILING_DIRECTORIES"}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", INVENTORY_GIT_EMPTY="")
    cmd = ["git", *(arg for item in GIT_SAFE_CONFIG for arg in ("-c", item)), *options, *args]
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120,
                             env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def split_index(root):
    """True when the index is stored split (`sharedindex.*` beside it).

    Every git command that reads a split index bumps the shared file's mtime,
    whatever the locks or config, so the index must not be read at all.
    Leftover shared files from an earlier split also count: a false positive
    only costs the dirty state. rev-parse and the history commands read no index.
    """
    for gitdir in (git(["rev-parse", "--git-dir", "--git-common-dir"], root) or "").splitlines():
        try:
            names = os.listdir(os.path.join(root, gitdir))
        except OSError:
            continue
        if any(name.startswith("sharedindex.") for name in names):
            return True
    return False


def git_status(root):
    """`git status --porcelain` with every configured filter driver disabled.

    Status re-hashes stat-dirty and racily clean files through clean/process
    filters, which run whatever command the config names, so each configured
    driver is blanked by name. `-c` splits at the first "=", so a driver name
    containing one needs --config-env (git 2.31+). Submodules are compared by
    commit only: checking their work trees spawns git under their own config.
    """
    options, names = [], set()
    for entry in (git(["config", "-z", "--get-regexp", r"^filter\."], root) or "").split("\0"):
        key = entry.split("\n", 1)[0]
        names.add(key[len("filter."):key.rfind(".")])
    for name in sorted(n for n in names if n):
        for var in ("clean", "process", "required"):
            key = f"filter.{name}.{var}"
            options += [f"--config-env={key}=INVENTORY_GIT_EMPTY"] if "=" in name else ["-c", f"{key}="]
    return git(["status", "--porcelain", "--untracked-files=all", "--ignore-submodules=dirty"], root, options)


def dirty_state(root):
    if split_index(root):
        return {"dirty": None, "dirty_count": None, "dirty_files": [], "dirty_fingerprint": None,
                "dirty_unknown": "split index: reading it would bump sharedindex.* timestamps in SOURCE"}
    porcelain = git_status(root) or ""
    files = sorted(line[3:].split(" -> ")[-1].strip('"') for line in porcelain.splitlines() if line.strip())
    digest = hashlib.sha256()
    for f in files:
        digest.update(f.encode())
        path = os.path.join(root, f)
        if os.path.isfile(path):
            digest.update(file_digest(path))
    return {
        "dirty": bool(files),
        "dirty_count": len(files),
        "dirty_files": files[:200],
        "dirty_fingerprint": digest.hexdigest()[:16] if files else None,
    }


def stat_key(path):
    try:
        return file_id(os.lstat(path))
    except OSError:
        return None


def read_snapshot(path, limit=4 * 1024 * 1024):
    """Hash all bytes, retaining bounded text from the same read for inspection.

    Returns (digest, text, size, st). `st` is the path's lstat from before the
    read: the caller's final fence compares against it, so a write landing
    after this read still differs. Only regular files are opened; symlinks hash
    their target string and special files their type.
    """
    changed = ValueError(f"source changed during inventory: {path}; retry on a stable snapshot")
    try:
        st = os.lstat(path)
    except OSError:
        return b"unreadable", None, 0, None
    text = None
    try:
        if stat.S_ISLNK(st.st_mode):
            link = os.fsencode(os.readlink(path))
            digest, size = hashlib.sha256(b"symlink:" + link).digest(), len(link)
        elif not stat.S_ISREG(st.st_mode):
            digest, size = f"special:{stat.S_IFMT(st.st_mode):o}".encode(), 0
        else:
            fh = open_regular(path, st)
            if fh is None:
                raise changed
            sha, chunks, size = hashlib.sha256(), [], 0
            with fh:
                for chunk in iter(lambda: fh.read(64 * 1024), b""):
                    sha.update(chunk)
                    size += len(chunk)
                    if size <= limit:
                        chunks.append(chunk)
                    else:
                        chunks.clear()
                if file_id(os.fstat(fh.fileno())) != file_id(st):
                    raise changed
            digest, data = sha.digest(), b"".join(chunks)
            if size <= limit and b"\x00" not in data[:4096]:
                text = data.decode("utf-8", errors="replace")
    except OSError:
        return b"unreadable", None, 0, st
    if stat_key(path) != file_id(st):
        raise changed
    return digest, text, size, st


def file_digest(path):
    return read_snapshot(path, limit=0)[0]


def git_signals(root, max_commits):
    head = git(["rev-parse", "HEAD"], root)
    if head is None:
        return {"available": False}
    info = {
        "available": True,
        "sha": head.strip(),
        "branch": (git(["rev-parse", "--abbrev-ref", "HEAD"], root) or "").strip(),
        **dirty_state(root),
        "commit_count": int((git(["rev-list", "--count", "HEAD"], root) or "0").strip() or 0),
        "first_commit": (git(["log", "--reverse", "--format=%as", "--max-parents=0"], root) or "").split("\n")[0],
        "last_commit": (git(["log", "-1", "--format=%as"], root) or "").strip(),
        "contributors": len(set((git(["log", "--format=%ae", f"-n{max_commits}"], root) or "").split())),
    }
    log = git(["log", f"-n{max_commits}", "--no-merges", "--no-ext-diff", "--no-textconv", "--name-only",
               "--format=@@%H\t%s"], root) or ""
    commits, current = [], None
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, _, subject = line[2:].partition("\t")
            current = {"sha": sha, "subject": subject, "files": []}
            commits.append(current)
        elif line.strip() and current is not None:
            name = line.strip()
            if os.path.basename(name) not in LOCKFILES and lang_of(name):
                current["files"].append(name)
    changes, fixes = Counter(), Counter()
    pair_counts = Counter()
    for c in commits:
        files = sorted(set(c["files"]))
        for f in files:
            changes[f] += 1
            if FIX_RE.search(c["subject"]):
                fixes[f] += 1
        if 2 <= len(files) <= 30:
            for a, b in combinations(files, 2):
                pair_counts[(a, b)] += 1
    info["hotspots"] = [
        {"file": f, "changes": n, "fix_commits": fixes[f]}
        for f, n in changes.most_common(25)
    ]
    pairs = []
    for (a, b), n in pair_counts.items():
        if n < 3:
            continue
        jac = n / float(changes[a] + changes[b] - n)
        if jac >= 0.3:
            pairs.append({"a": a, "b": b, "together": n, "jaccard": round(jac, 2)})
    pairs.sort(key=lambda p: (-p["together"], -p["jaccard"], p["a"]))
    info["co_change"] = pairs[:25]
    info["fix_subjects_sample"] = [c["subject"] for c in commits if FIX_RE.search(c["subject"])][:30]
    info["commits_scanned"] = len(commits)
    info["shallow_repository"] = (git(["rev-parse", "--is-shallow-repository"], root) or "").strip() == "true"
    info["hotspots_suppressed"] = len(commits) < 20 or info["shallow_repository"]
    if info["hotspots_suppressed"]:
        info["hotspots"] = []
        info["co_change"] = []
        info["hotspots_suppression_reason"] = f"history too shallow ({len(commits)} commits); hotspots suppressed"
        if info["shallow_repository"]:
            info["hotspots_suppression_reason"] += " (shallow repository)"
    return info


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

TEST_CONFIG_RX = re.compile("|".join(fnmatch.translate(p) for p in ("*.json", ".eslintrc*", "tsconfig*", "*.config.*")))


def compiled_entry_globs():
    """ENTRY_GLOBS as (regex, basename_only, category); same semantics as matches()."""
    return [(re.compile(fnmatch.translate(p)), "/" not in p, cat) for p, cat in ENTRY_GLOBS]


def matches(relpath, pattern):
    """Slash-less patterns match the basename only; others match the relative path.

    A trailing "/*" also matches nested files (fnmatch's * already crosses "/").
    """
    if "/" not in pattern:
        return fnmatch.fnmatch(os.path.basename(relpath), pattern)
    return fnmatch.fnmatch(relpath, pattern)


def scan_steering(root, skip=None):
    """Steering files under `root`; `skip` is a directory whose subtree is left out."""
    found = []
    if not root or not os.path.isdir(root):
        return found
    for path in walk(root):
        if skip and (path == skip or path.startswith(skip + os.sep)):
            continue
        r = rel(path, root)
        if any(fnmatch.fnmatch(r, g) for g in STEERING_GLOBS):
            text = read_text(path, 64 * 1024) or ""
            first = next((ln.strip("# ").strip() for ln in text.splitlines()
                          if ln.strip() and ln.strip() != "---" and not ln.startswith("name:")), "")
            try:
                size = os.lstat(path).st_size
            except OSError:
                size = None
            found.append({"path": r, "bytes": size, "first_line": first[:160],
                          "skipped_symlink": os.path.islink(path)})
    unique = {}
    for f in found:
        if f["path"].startswith((".amp/", ".git/")):
            continue
        if f["path"] not in unique or (f["first_line"] and not unique[f["path"]]["first_line"]):
            unique[f["path"]] = f
    return sorted(unique.values(), key=lambda x: x["path"])


def find_app_roots(files):
    """Directories holding a primary manifest; fixture/test roots are flagged, not dropped."""
    roots = {}
    for r in files:
        name = os.path.basename(r)
        if name in PRIMARY_MANIFESTS or name.endswith(".csproj"):
            d = os.path.dirname(r) or "."
            roots.setdefault(d, {"path": d, "fixture": bool(FIXTURE_ROOT_RE.search(d)), "manifests": []})
            roots[d]["manifests"].append(name)
    if "." not in roots:
        roots["."] = {"path": ".", "fixture": False, "manifests": []}
    return dict(sorted(roots.items()))


def nearest_root(relpath, roots):
    best = "."
    for d in roots:
        if d != "." and (relpath == d or relpath.startswith(d + "/")) and len(d) > len(best):
            best = d
    return best


def spread_sample(items, cap):
    """Round-robin across files so a capped sample spans the codebase, not the first directories."""
    by_file = defaultdict(list)
    for item in items:
        by_file[item.split(":", 1)[0]].append(item)
    queues = [by_file[f] for f in sorted(by_file)]
    out, i = [], 0
    while len(out) < cap and any(queues):
        q = queues[i % len(queues)]
        if q:
            out.append(q.pop(0))
        i += 1
    return sorted(out)


def detect_stacks(root_abs, deps, direct, csproj_seen):
    stack_deps = direct or deps
    found = []
    for stack, markers in STACK_MARKERS.items():
        evidence = []
        for kind, value in markers:
            if kind == "file" and os.path.exists(os.path.join(root_abs, value)):
                evidence.append(f"file:{value}")
            elif kind == "dep" and any(fnmatch.fnmatch(d, value) for d in stack_deps):
                evidence.append(f"dep:{value}")
            elif kind == "glob" and value == "*.csproj" and csproj_seen:
                evidence.append("file:*.csproj")
        if evidence:
            found.append({"stack": stack, "evidence": evidence})
    return found


def inventory(source, target, max_commits, steering_dirs=()):
    source = os.path.abspath(source)
    head_before = git(["rev-parse", "HEAD"], source)
    status_before = None if split_index(source) else git_status(source)
    files = [rel(p, source) for p in walk(source)]
    roots = find_app_roots([r for r in files if not os.path.islink(os.path.join(source, r))])
    loc_by_lang, files_by_lang = Counter(), Counter()
    entry, entry_seen = defaultdict(list), Counter()
    root_entries = defaultdict(Counter)
    manifests, unparsed, regex_fallback = {}, [], []
    manifest_counts, skipped_symlinks, skipped_special = {}, [], []
    root_deps = defaultdict(lambda: {"all": set(), "direct": set(), "csproj": False})
    hint_hits = defaultdict(lambda: {"count": 0, "files": Counter()})
    why_all, todo_count = [], 0
    skipped = Counter()
    tree = hashlib.sha256()
    stat_before = {}
    entry_globs = compiled_entry_globs()

    for r in files:
        path = os.path.join(source, r)
        name = os.path.basename(r)
        root = nearest_root(r, roots)
        app_rel = r if root == "." else r[len(root) + 1:]
        parser = manifest_parser(app_rel, name)
        digest, text, size, st = read_snapshot(path, 4 * 1024 * 1024 if parser else MAX_SCAN_BYTES)
        tree.update(r.encode())
        tree.update(digest)
        stat_before[r] = file_id(st) if st else None
        if st and stat.S_ISLNK(st.st_mode):
            skipped_symlinks.append({"path": r, "target": os.readlink(path)})
            continue
        kind = special_type(st.st_mode) if st else None
        if kind:
            skipped_special.append({"path": r, "type": kind})
            continue
        lang = lang_of(name)
        category = None
        test_config = bool(TEST_CONFIG_RX.match(name))
        for rx, basename_only, cat in entry_globs:
            if cat == "tests" and test_config:
                continue
            if (rx.match(name) if basename_only else (rx.match(r) or (app_rel != r and rx.match(app_rel)))):
                category = cat
                entry_seen[cat] += 1
                root_entries[root][cat] += 1
                if len(entry[cat]) < ENTRY_CAP:
                    entry[cat].append(r)
                break
        if parser:
            if text is not None:
                found = parser(text)
                if isinstance(found, Fallback):
                    unparsed.append(r)
                    regex_fallback.append(r)
                parsed = sorted(set(found))
                manifests[r] = parsed[:ENTRY_CAP]
                manifest_counts[r] = {"discovered": len(parsed), "returned": len(manifests[r])}
                bucket = root_deps[root]
                bucket["all"].update(dep_name(d) for d in parsed)
                if name not in LOCK_MANIFESTS:
                    bucket["direct"].update(dep_name(d) for d in parsed)
                bucket["csproj"] = bucket["csproj"] or name.endswith(".csproj")
            else:
                unparsed.append(r)
        elif any(fnmatch.fnmatch(name, pat) for pat in UNPARSED_MANIFESTS):
            unparsed.append(r)
        if not lang:
            continue
        if text is None or size > MAX_SCAN_BYTES:
            skipped["oversized_or_binary"] += 1
            continue
        loc = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        loc_by_lang[lang] += loc
        files_by_lang[lang] += 1
        if category == "tests" or (lang not in SOURCE_LANGS and lang not in {"erb", "haml", "slim", "blade", "heex"}):
            continue
        todo_count += len(re.findall(r"\b(TODO|FIXME|HACK|XXX)\b", text))
        for label, (langs, rx) in MECHANISM_HINTS.items():
            if lang not in langs:
                continue
            n = len(re.findall(rx, text))
            if n:
                hint_hits[label]["count"] += n
                hint_hits[label]["files"][r] += n
        for i, line in enumerate(text.splitlines(), 1):
            if len(line) < 400 and WHY_COMMENT_RE.search(line) and not line.strip().startswith(("http", "import")):
                why_all.append(f"{r}:{i}: {line.strip()[:200]}")

    production_deps = [b for d, b in root_deps.items() if not roots[d]["fixture"]]
    all_deps = set().union(*(b["all"] for b in production_deps))
    all_direct = set().union(*(b["direct"] for b in production_deps))
    app_roots, stack_index = [], {}
    shape_hints = set()
    for d, info in roots.items():
        bucket = root_deps.get(d, {"all": set(), "direct": set(), "csproj": False})
        root_signals = {s for s, (_, patterns) in SIGNALS.items()
                        if any(fnmatch.fnmatch(dep, p) for dep in bucket["all"] for p in patterns)}
        root_shapes = app_shape_hints(root_entries[d], root_signals)
        if not info["fixture"]:
            shape_hints.update(root_shapes)
        found = detect_stacks(os.path.join(source, d), bucket["all"], bucket["direct"], bucket["csproj"])
        if not found and not info["manifests"]:
            continue
        languages = sorted({LANGUAGE_BY_MANIFEST[m] for m in info["manifests"] if m in LANGUAGE_BY_MANIFEST}
                           | ({"dotnet"} if any(m.endswith(".csproj") for m in info["manifests"]) else set()))
        if not found:
            found = [{"stack": f"{lang} (no framework pack matched)", "evidence": ["manifest"]} for lang in languages]
        app_roots.append({**info, "languages": languages, "stacks": [s["stack"] for s in found],
                          "shape_hints": root_shapes,
                          "direct_deps": len(bucket["direct"])})
        if info["fixture"]:
            continue
        for s in found:
            merged = stack_index.setdefault(s["stack"], {"stack": s["stack"], "pack": stack_pack(s["stack"]),
                                                          "evidence": [], "roots": []})
            merged["evidence"] += [e for e in s["evidence"] if e not in merged["evidence"]]
            merged["roots"].append(d)
    order = list(STACK_MARKERS)
    stacks = sorted(stack_index.values(), key=lambda s: (order.index(s["stack"]) if s["stack"] in order else 99, s["stack"]))

    signals = []
    for signal, (category, patterns) in SIGNALS.items():
        hits = sorted(d for d in all_deps if any(fnmatch.fnmatch(d, p) for p in patterns))
        if hits:
            via = "direct" if any(h in all_direct for h in hits) or not all_direct else "transitive"
            signals.append({"signal": signal, "category": category, "via": via, "deps": hits[:10]})

    hints = {
        label: {"count": v["count"], "files": len(v["files"]),
                "top_files": [f for f, _ in v["files"].most_common(HINT_TOP)]}
        for label, v in sorted(hint_hits.items(), key=lambda kv: -kv[1]["count"])
    }
    why_comments = spread_sample(why_all, WHY_CAP)
    git_info = git_signals(source, max_commits)
    steering = {"source": scan_steering(source), "target": scan_steering(os.path.abspath(target)) if target else []}
    # Extra roots (e.g. the repo holding a `reference/` checkout); SOURCE itself is already scanned.
    steering["extra"] = [
        dict(f, root=os.path.abspath(d))
        for d in steering_dirs
        for f in scan_steering(os.path.abspath(d), skip=source)
    ]
    # Any write bumps mtime/ctime, so metadata detects edits made during the scan without re-reading.
    stat_after = {rel(path, source): stat_key(path) for path in walk(source)}
    if (stat_after != stat_before or head_before != git(["rev-parse", "HEAD"], source)
            or status_before != (None if split_index(source) else git_status(source))):
        raise ValueError("source changed during inventory; retry on a stable snapshot")

    coverage = {
        "files_walked": len(files),
        "skipped_dirs": sorted(SKIP_DIRS),
        "skipped_files": dict(skipped),
        "skipped_symlinks": skipped_symlinks,
        "skipped_special_files": skipped_special,
        "manifests": manifest_counts,
        "entry_points": {c: {"discovered": entry_seen[c], "returned": len(entry[c])} for c in sorted(entry)},
        "why_comments": {"discovered": len(why_all), "returned": len(why_comments), "sampling": "round-robin by file"},
        "mechanism_hints": {k: {"files": v["files"], "returned": len(v["top_files"])} for k, v in hints.items()},
        "hint_languages": sorted(SOURCE_LANGS),
        "unparsed_manifests": sorted(unparsed),
        "git_commits_scanned": git_info.get("commits_scanned", 0),
        "limitations": [
            "regex hints are leads; absence of a hint is not absence of the mechanism",
            "tests, SQL, triggers and stored procedures are not scanned for mechanism hints",
            "dynamic dispatch, metaprogramming and generated routes need manual tracing",
        ],
    }
    if skipped_symlinks:
        coverage["limitations"].append(f"{len(skipped_symlinks)} symlinks not followed; linked content is outside coverage")
    if skipped_special:
        coverage["limitations"].append(f"{len(skipped_special)} special files not read (FIFOs, sockets, devices); "
                                       "their content is outside coverage")
    if regex_fallback:
        coverage["limitations"].append(
            f"{len(regex_fallback)} TOML manifests read by regex fallback (invalid TOML, or no tomllib before "
            "Python 3.11); their dependency lists may be incomplete: " + ", ".join(regex_fallback[:10]))
    if git_info.get("hotspots_suppressed"):
        coverage["limitations"].append(git_info["hotspots_suppression_reason"])
    if git_info.get("dirty_unknown"):
        coverage["limitations"].append(f"dirty state unknown ({git_info['dirty_unknown']}); "
                                       "tree_fingerprint still covers every scanned file")

    return {
        "version": 2,
        "tool": "rewrite-inventory",
        "source": {"path": source, "git": git_info, "tree_fingerprint": tree.hexdigest()[:16]},
        "size": {
            "files": len(files),
            "loc_by_language": dict(loc_by_lang.most_common()),
            "files_by_language": dict(files_by_lang.most_common()),
        },
        "app_roots": app_roots,
        "stacks": stacks,
        "shape_hints": sorted(shape_hints),
        "manifests": manifests,
        "infra_signals": signals,
        "entry_points": {k: v for k, v in sorted(entry.items())},
        "mechanism_hints": hints,
        "why_comments": why_comments,
        "todo_fixme_hack_count": todo_count,
        "steering": steering,
        "coverage": coverage,
    }


def app_shape_hints(entry_seen, signal_names):
    """Leads for references/app-shapes.md; the cartographer confirms the shape from code."""
    hints = []
    if entry_seen["views"] or entry_seen["frontend"]:
        hints.append("web-ui")
    # Go `handler.go` files are HTTP handlers unless the app only consumes messages.
    consumer = bool(signal_names & {"kafka", "rabbitmq", "sqs/sns"})
    go_http = entry_seen["handlers"] and ("go-http" in signal_names or not consumer)
    if entry_seen["routes"] or entry_seen["controllers"] or go_http:
        hints.append("http-api" if not entry_seen["views"] else "web-app")
    if entry_seen["realtime"] or signal_names & {"actioncable/anycable", "socket.io/ws", "signalr",
                                                  "django-channels", "pusher/reverb/echo"}:
        hints.append("realtime")
    if entry_seen["jobs"] or signal_names & {"kafka", "rabbitmq", "sqs/sns"}:
        hints.append("worker/consumer")
    if entry_seen["scheduling"] or "cron" in signal_names:
        hints.append("scheduled-jobs")
    for signal, shape in (("cli", "cli"), ("data-pipeline", "data-pipeline"), ("ml-inference", "ml-inference"),
                          ("desktop", "desktop"), ("serverless", "serverless"), ("multi-tenancy", "multi-tenant")):
        if signal in signal_names:
            hints.append(shape)
    return hints


def identity(inv):
    g = inv["source"]["git"]
    return {
        "sha": g.get("sha"),
        "dirty_fingerprint": g.get("dirty_fingerprint"),
        "tree_fingerprint": inv["source"].get("tree_fingerprint"),
    }


def compare(prev, cur):
    """Identity changes between two inventories; empty list means the same snapshot."""
    a, b = identity(prev), identity(cur)
    return [f"{k}: {a[k]} -> {b[k]}" for k in a if a[k] != b[k]]


def to_markdown(inv):
    g = inv["source"]["git"]
    cov = inv["coverage"]
    lines = [f"# Inventory: {inv['source']['path']}", ""]
    if g.get("available"):
        lines.append(f"- git: `{g['sha'][:12]}` on `{g['branch']}`, {g['commit_count']} commits, "
                     f"{g['first_commit']} → {g['last_commit']}, {g['contributors']} contributors"
                     + (f" (**dirty tree**: {g['dirty_count']} files, fingerprint `{g['dirty_fingerprint']}`)"
                        if g["dirty"] else "")
                     + (" (dirty state unknown: split index)" if g["dirty"] is None else ""))
    else:
        lines.append("- git: not a repository (no history signals)")
    lines.append(f"- tree fingerprint: `{inv['source']['tree_fingerprint']}`")
    lines.append("- stacks: " + (", ".join(
        f"{s['stack']} ({'; '.join(s['evidence'])}{'' if s['roots'] == ['.'] else ' in ' + ', '.join(s['roots'])})"
        for s in inv["stacks"]) or "unknown"))
    packs = sorted({s["pack"] for s in inv["stacks"]}) or ["stacks/generic.md"]
    lines.append("- stack packs to read: " + ", ".join(f"`{p}`" for p in packs))
    lines.append("- shape hints (confirm in code): " + (", ".join(inv["shape_hints"]) or "none"))
    loc = inv["size"]["loc_by_language"]
    lines.append(f"- size: {inv['size']['files']} files; LOC " + ", ".join(f"{k} {v}" for k, v in list(loc.items())[:8]))
    if len(inv["app_roots"]) > 1:
        lines += ["", "## Application roots", ""]
        for root in inv["app_roots"]:
            tag = " _(test/fixture)_" if root["fixture"] else ""
            lines.append(f"- `{root['path']}`{tag}: {', '.join(root['stacks']) or 'no stack'} "
                         f"({', '.join(root['manifests']) or 'no manifest'})")
    lines += ["", "## Infrastructure signals", ""]
    for s in inv["infra_signals"]:
        tag = "" if s.get("via") == "direct" else " _(transitive only)_"
        lines.append(f"- **{s['signal']}** ({s['category']}){tag}: {', '.join(s['deps'])}")
    lines += ["", "## Entry points", ""]
    for cat, files in inv["entry_points"].items():
        seen = cov["entry_points"][cat]["discovered"]
        more = f" (returned {len(files)} of {seen})" if seen > len(files) else ""
        lines.append(f"- {cat}: {seen}{more} — " + ", ".join(files[:5]) + (" …" if len(files) > 5 else ""))
    lines += ["", "## Mechanism hints (pattern counts — leads, not conclusions)", ""]
    for label, h in inv["mechanism_hints"].items():
        lines.append(f"- {label}: {h['count']} in {h['files']} files — " + ", ".join(h["top_files"][:4]))
    steer = inv["steering"]
    lines += ["", "## Agent-steering files", ""]
    for side in ("source", "target", "extra"):
        for f in steer.get(side, []):
            path = os.path.join(f["root"], f["path"]) if side == "extra" else f["path"]
            lines.append(f"- [{side}] `{path}` {('— ' + f['first_line']) if f['first_line'] else ''}")
    if not any(steer.get(side) for side in ("source", "target", "extra")):
        lines.append("- none found in SOURCE, TARGET or `--steering` roots; files elsewhere "
                     "(e.g. above a `reference/` checkout) need `--steering DIR`")
    if g.get("available"):
        lines += ["", "## Git hotspots (top 10)", ""]
        if g.get("hotspots_suppressed"):
            lines.append("- " + g["hotspots_suppression_reason"])
        for h in g["hotspots"][:10]:
            lines.append(f"- {h['file']}: {h['changes']} changes, {h['fix_commits']} fix commits")
        if g["co_change"]:
            lines += ["", "## Co-change pairs (candidate shared boundaries)", ""]
            for p in g["co_change"][:10]:
                lines.append(f"- {p['a']} ↔ {p['b']}: {p['together']}× (J={p['jaccard']})")
    why = cov["why_comments"]
    lines += ["", "## Coverage and limits", "",
              f"- files walked: {cov['files_walked']}; skipped oversized/binary source files: "
              f"{cov['skipped_files'].get('oversized_or_binary', 0)}",
              f"- why-comments: returned {why['returned']} of {why['discovered']} ({why['sampling']}); "
              f"TODO/FIXME/HACK: {inv['todo_fixme_hack_count']}",
              f"- git commits scanned: {cov['git_commits_scanned']}"]
    if cov["unparsed_manifests"]:
        lines.append("- unparsed manifests (deps unknown, not absent): " + ", ".join(cov["unparsed_manifests"][:10]))
    for path, counts in cov["manifests"].items():
        if counts["discovered"] > counts["returned"]:
            lines.append(f"- manifest `{path}`: returned {counts['returned']} of {counts['discovered']} dependencies")
    lines += [f"- {text}" for text in cov["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="path to the legacy application (read-only)")
    ap.add_argument("--target", help="path to the Elixir target project (scanned for steering files)")
    ap.add_argument("--steering", action="append", default=[], metavar="DIR",
                    help="extra directory to scan for agent-steering files (repeatable)")
    ap.add_argument("--json", dest="json_out", help="write JSON inventory here")
    ap.add_argument("--md", dest="md_out", help="write Markdown summary here")
    ap.add_argument("--max-commits", type=int, default=2000)
    ap.add_argument("--compare", metavar="PREV.json",
                    help="print identity changes against a previous inventory; exit 1 if the snapshot changed")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.source):
        print(f"error: {args.source} is not a directory", file=sys.stderr)
        return 2
    src = os.path.realpath(args.source)
    for out in (args.json_out, args.md_out):
        if out and os.path.realpath(out).startswith(src + os.sep):
            print("error: refusing to write inside SOURCE (the legacy app is read-only)", file=sys.stderr)
            return 2
    try:
        inv = inventory(args.source, args.target, args.max_commits, args.steering)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.compare:
        with open(args.compare, encoding="utf-8") as fh:
            changes = compare(json.load(fh), inv)
        print("\n".join(changes) if changes else "unchanged")
        return 1 if changes else 0
    md = to_markdown(inv)
    for out, content in ((args.json_out, json.dumps(inv, indent=2) + "\n"), (args.md_out, md)):
        if out:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(content)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
