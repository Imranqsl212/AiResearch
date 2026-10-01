# Исследование: как AI-агент исправляет криптографические ошибки и когда останавливается

## Идея в двух предложениях

Мы не пытаемся доказать, что «AI умеет или не умеет кибербезопасность» вообще.
Это слишком широкая тема. Мы берём конкретный контролируемый сценарий: локальный
AI coding agent получает небезопасную реализацию криптографического механизма,
получает обратную связь от независимого security checker и пытается исправить код.

Главный вопрос: после неудачи агент действительно меняет security strategy или
только перебирает параметры, повторяет тот же подход и останавливается случайно —
по timeout/budget или после неподтверждённого заявления об успехе?

## Что именно мы измеряем

Для каждой попытки сохраняются только наблюдаемые события:

- какой tool вызван;
- какие параметры и код отправлены;
- что ответил независимый checker;
- прошёл ли код executable verifier;
- изменилась ли реализация и observable strategy codebook;
- повторил ли агент прежнее действие;
- сменил ли tool/гипотезу/подход;
- когда и почему остановился;
- заявил ли успех без verifier evidence.

Private chain-of-thought не собирается и не используется как доказательство.
Финальный текст модели — это только claim, а не ground truth.

## Дизайн benchmark

В текущем executable catalog 80 локальных задач:

- 12 crypto families × 4 conditions = 48 задач;
- 8 local web-security families × 4 conditions = 32 задачи;
- всего 20 семейств, каждое с одинаковым matched four-cell дизайном.

| Условие | Цель достижима? | Feedback |
|---|---:|---|
| `RD` | да | diagnostic: checker сообщает полезное направление |
| `UD` | нет | diagnostic: checker сообщает полезное направление |
| `RW` | да | weak but truthful: checker подтверждает только факт rejection |
| `UW` | нет | weak but truthful: checker подтверждает только факт rejection |

`RD/RW` — repairable, `UD/UW` — evaluator-enforced unreachable. Это важно:
агент не получает label условия, expected outcome или состояние verifier. Для
`UD/UW` нельзя «выиграть» бесконечными попытками, поэтому можно отдельно измерять,
распознаёт ли агент невозможность задачи.

Примеры crypto families: AEAD/nonce lifecycle, key management, weak randomness,
key derivation, password hashing, padding, tag verification, TLS/certificate
validation, secret leakage и IV generation. Web-секция — это не сканирование
Интернета, а локальные request-handler fixtures для SQL injection, XSS,
path traversal, SSRF policy, command injection, authorization, session и CSRF.

## Как защищён эксперимент

Модель работает через loopback Ollama (`qwen3:4b`) и получает только публичную
проекцию task. Код, который она предлагает, исполняется в свежем Docker container:

- `network=none`;
- без host mounts;
- без SSH/cloud/API credentials;
- read-only root filesystem;
- отдельные `/tmp` и `/work`;
- ограничение CPU, memory, PIDs и file descriptors;
- timeout и принудительное удаление контейнера;
- immutable digest-pinned image;
- fail-closed safety gate.

Официальная safety suite уже проверила network isolation, host filesystem,
credentials, limits, timeout, runaway processes, log retention, reproducibility и
точно тот candidate RPC path, который используется benchmark.

## Порядок запуска

Ночная команда сначала делает preflight:

1. проверяет, что локальный Ollama содержит выбранную модель;
2. проверяет все 80 task definitions и vulnerable/secure references;
3. запускает официальный Docker safety suite;
4. запускает один исключённый provider→Docker→verifier smoke;
5. запускает pilot на 12 задачах: `aead`, `key-derivation`, `sqli` × `RD/UD/RW/UW`;
6. проверяет completeness, receipts, logs и отсутствие infrastructure abort;
7. только после этого, если передан `--run-main`, запускает main на всех 80 задачах.

Pilot и main используют create-once manifest, deterministic schedule, attempt ledger
и append-only raw JSONL. При остановке процесс можно повторить: завершённые slots
будут пропущены. Незавершённая reservation не обходится автоматически — это
намеренный fail-closed режим, чтобы не потерять или не продублировать наблюдение.

## Команда для ночного запуска

Из корня проекта:

```bash
cd /Users/imranmzakirov/Desktop/research && \
PYTHONDONTWRITEBYTECODE=1 python3 -u -B -m experiments.run_nightly_study \
  --model qwen3:4b \
  --pilot-runs 1 \
  --main-runs 3 \
  --request-timeout 300 \
  --timeout-seconds 900 \
  --max-steps 8 \
  --run-main
```

Если сначала нужен только pilot, уберите последний флаг `--run-main`. Это
рекомендуемый первый запуск: main тогда не начнётся автоматически.

`--request-timeout 300` — это лимит одного запроса к Ollama. `--timeout-seconds 900`
— лимит всего episode. На MacBook Air M1 8 GB Qwen3:4b может тратить несколько
минут на один tool decision, поэтому полный main не гарантированно помещается в
одну ночь. Команда resumable и продолжает frozen schedule с последнего валидного
slot; она не меняет задачи по ходу дела.

## Где смотреть результат утром

Главный orchestration report:

```text
experiments/nightly/<UTC-timestamp>.json
```

Frozen research metadata:

```text
experiments/manifests/executable-pilot-v0-5-0.json
experiments/schedules/executable-pilot-v0-5-0.json
experiments/manifests/executable-main-v0-5-0.json
experiments/schedules/executable-main-v0-5-0.json
```

Результаты и integrity ledger:

```text
experiments/results/executable-pilot-v0-5-0.jsonl
experiments/ledgers/executable-pilot-v0-5-0.json
experiments/results/executable-main-v0-5-0.jsonl
experiments/ledgers/executable-main-v0-5-0.json
```

Сырые trajectories находятся в `experiments/runs/`, receipts — рядом с ними,
content-addressed archive — в `experiments/raw_archive/`. Эти директории намеренно
игнорируются Git и не должны публиковаться без отдельного data-release review.

Успехом считается только `verifier_terminal_outcome=VALIDATED_SUCCESS`. Статусы
`TIMEOUT`, `BUDGET_STOP`, `AGENT_SELF_TERMINATION`, `INFRASTRUCTURE_ABORT` и
unsupported claim сохраняются отдельно; они не смешиваются в один «AI failed».

## Как читать исследовательский результат

Мы не будем писать «модель поняла безопасность» по одному успешному коду. Сначала
проверим:

- меняет ли она underlying strategy после failure;
- различаются ли RD/RW и UD/UW при сопоставимой сложности;
- сколько попыток — настоящая адаптация, а сколько — surface-level mutation;
- прекращает ли она поиск после накопления negative evidence;
- насколько часто claim success не подтверждается verifier;
- объясняются ли эффекты timeout, tool errors или task difficulty.

Все итоговые числа должны быть воспроизводимы из raw trajectories кодом в
`analysis/`. Pilot не является headline result: его задача — найти confounders,
ошибки verifier, проблемы logging и слишком медленные части protocol.

## Что увидит ментор/соавтор в public repository

- `docs/CRYPTO_PROTOCOL.md` — формальный protocol и estimand;
- `docs/EXECUTABLE_CATALOG.md` — описание 80 local tasks;
- `docs/safety.md` — threat model и ограничения sandbox;
- `docs/RESEARCH_GUIDE_RU.md` — это краткое объяснение для чтения;
- `benchmark/` — schemas, generators и validators;
- `agent/` — provider-neutral adapter и Ollama integration;
- `sandbox/` — immutable runtime и safety tests;
- `experiments/` — manifests, schedule, ledger и launcher;
- `analysis/` и `paper/` — analysis/paper infrastructure без выдуманных main results.

## Честные ограничения

Сейчас это controlled local benchmark, а не доказательство поведения всех AI agents
и не оценка production crypto libraries. Модель одна, локальная, tasks synthetic but
executable, а strategy labels основаны только на observable codebook. Smoke success
подтверждает работоспособность pipeline, но не является научным выводом. Эти
ограничения являются частью исследования, а не скрываются из отчёта.
