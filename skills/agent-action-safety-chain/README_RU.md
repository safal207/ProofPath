# Agent Action Safety Chain — установка и использование

Это переносимый навык ChatGPT для аудита и завершения цепочек безопасности AI-агентов:

```text
proposal
→ intent / causal parent / scope / nonce / approval
→ ACCEPT / HOLD / BLOCK
→ выполнение только после ACCEPT
→ CML / LTP / durable ledger
→ evidence bundle
→ CI / review / merge
```

Навык подходит для NOOA, Codex, Claude Code, LangGraph, AutoGen, CrewAI, MCP и собственных tool-calling систем.

## Установка с телефона

### 1. Скачай готовый ZIP

Открой релиз:

```text
https://github.com/safal207/ProofPath/releases/tag/agent-action-safety-chain-v1.0.0
```

В блоке **Assets** скачай:

```text
agent-action-safety-chain.zip
```

Рядом публикуется файл контрольной суммы:

```text
agent-action-safety-chain.zip.sha256
```

### 2. Загрузи навык в ChatGPT

1. Открой мобильное приложение ChatGPT.
2. Перейди в раздел **Навыки**.
3. Открой **Созданные мной** или меню создания навыка.
4. Выбери **Загрузить** / **Upload skill**.
5. Укажи скачанный `agent-action-safety-chain.zip`.
6. После проверки установи или включи навык.

Название в списке:

```text
agent-action-safety-chain
```

## Как использовать в любом чате

После установки ChatGPT может подключать навык автоматически, когда запрос связан с агентной безопасностью, репозиториями, причинными трассами, replay, approval, evidence или CI.

Для явного вызова начни сообщение так:

```text
Используй навык agent-action-safety-chain.
```

### Аудит без изменений

```text
Используй навык agent-action-safety-chain.
Проверь репозиторий safal207/ExampleAgent на незамкнутые цепочки безопасности.
Только аудит: ничего не изменяй. Дай риски, доказательства и приоритеты.
```

### План реализации

```text
Используй навык agent-action-safety-chain.
Спроектируй proposal → guard → execution → causal audit → evidence для этого агента.
Сначала найди уже существующие компоненты и не создавай новый протокол без необходимости.
```

### Полная реализация до PR

```text
Используй навык agent-action-safety-chain.
Собери всю защитную цепочку в этом репозитории, добавь тесты и CI, открой PR.
Не мержи без моего отдельного разрешения.
```

### Полная реализация до merge

```text
Используй навык agent-action-safety-chain.
Доведи цепочку до конца: реализация, негативные тесты, evidence bundle, CI, устранение замечаний ревью и merge в main.
```

### Проверка существующего PR

```text
Используй навык agent-action-safety-chain.
Проверь PR #123: безопасность, replay, secret egress, path traversal, evidence integrity и честность заявлений.
Исправь подтверждённые проблемы и дождись зелёного CI.
```

## Что навык проверяет

- наличие `intent_id` и `parent_cause`;
- обязательный nonce и защиту от replay;
- scope и повышение полномочий;
- human approval для необратимых действий;
- secret-bearing network egress;
- выполнение side effect только после `ACCEPT`;
- разделение authorization и observation;
- причинные и replay-трассы;
- hash-linked ledger;
- уникальные и path-safe evidence bundles;
- SHA-256 manifest и обнаружение подмены;
- тесты, CI, review threads и mergeability.

## Доступ к репозиториям

Для работы с GitHub подключи приложение GitHub к ChatGPT и предоставь доступ к нужному репозиторию. Без GitHub-доступа навык всё равно может анализировать вставленный код, архив или текст diff, но не сможет создавать ветки, PR и merge.

Перед записью навык различает режимы:

```text
Audit only  — только анализ
Plan        — архитектура и план
Implement   — код и ветка
Validate    — тесты, CI и ревью
Merge       — merge только при явном разрешении
```

## Честные границы

Навык предназначен для defensive-задач. Он не должен:

- читать или передавать реальные секреты в тестах;
- создавать эксплуатационные payload'ы;
- выдавать Python guard за OS sandbox;
- придумывать результаты тестов, CI или ревью;
- заявлять официальный vendor endorsement без доказательств;
- переносить результаты синтетического benchmark на production как гарантию безопасности.

## Сборка ZIP из исходников

Из корня ProofPath:

```bash
python3 scripts/build_agent_action_safety_chain_skill.py
```

Результат:

```text
dist/agent-action-safety-chain.zip
dist/agent-action-safety-chain.zip.sha256
```

Workflow `.github/workflows/publish-agent-action-safety-chain-skill.yml` автоматически проверяет пакет и публикует его в GitHub Release.
