# Three-Graph Agent Safety v1.2 — установка в ChatGPT

Навык моделирует важные действия агента через девять независимых причинных графов.

```text
Истина:
Идея + Намерение + Факт

Контроль:
Личность + Политика + Возможности + Память + Время + Риск
```

## Главная защита

```text
Подтверждённая личность ≠ разрешение
Доступная возможность ≠ разрешение
Запись времени ≠ актуальность
Память ≠ намерение
UNKNOWN ≠ SUCCESS
```

Агент получает `ACCEPT` только когда одновременно подтверждены:

```text
кто действует
что пользователь сейчас разрешил
какая политика действует
какой capability будет использован
привязан ли capability к реальному executor
действительны ли все временные окна
приемлем ли остаточный риск
```

После выполнения нужен отдельный Fact Graph и независимая проверка результата.

## Установка

1. Открой релиз `three-graph-agent-safety-v1.2.0` в ProofPath.
2. Скачай `three-graph-agent-safety.zip`.
3. В ChatGPT открой **Настройки → Навыки → Созданные мной**.
4. Добавь ZIP целиком, не распаковывая его.

## Быстрые команды

```text
Построй девять графов безопасности для этого действия:
Idea, Intent, Identity, Policy, Capability, Memory,
Temporal, Risk и Fact.
```

```text
Проверь, совпадает ли текущая личность с principal в Intent,
и привязан ли выбранный capability к реальному executor.
```

```text
Проверь все временные окна перед dispatch:
сессию, Intent, Policy, approval, capability lease и deadline.
```

```text
Найди, где техническая возможность была ошибочно принята за разрешение.
```

```text
Разбери timeout. Сохрани UNKNOWN, повторно проверь Identity,
Intent, Policy, Capability и Temporal, затем выполни readback.
```

```text
Создай Personal Agent Safety v1.2 bundle,
прогони semantic validator и негативные сценарии.
```

## Формат ответа

```text
1. Idea Graph
2. Intent Graph
3. Identity Graph
4. Policy Graph
5. Capability Graph
6. Memory Graph
7. Temporal Graph
8. Risk Graph
9. Fact Graph
10. Mismatches
11. Decision
12. Recovery
13. Independent verification
14. Next safe action
```

## Машинный контракт

```text
assets/personal-agent-safety-v1.2-bundle.schema.json
assets/personal-agent-safety.example.json
tools/validate_personal_agent_safety_bundle.py
```

Проверка:

```bash
python3 tools/validate_personal_agent_safety_bundle.py \
  assets/personal-agent-safety.example.json \
  --self-test
```

## Важно

Навык не является системной песочницей, IAM-системой или доказательством личности сам по себе. Он не создаёт полномочия и не выполняет внешние действия. Реальные побочные эффекты должны оставаться за внешней авторизацией, минимальным capability, актуальной identity/session binding, временной проверкой, sandbox/VM/container и authoritative system of record.
