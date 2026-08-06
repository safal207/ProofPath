# ProofPath — All Chats Master Context v0.3

**Дата консолидации:** 2026-08-02  
**Статус:** канонический рабочий документ  
**Назначение:** единый контекст для GitHub, продукта, протокола, пилотов, инвесторов, партнёров и дальнейшей разработки  
**Основной продукт:** ProofPath Assured Action Protocol  
**Первый коммерческий сценарий:** допуск AI coding/cloud agent к production deployment  
**Каноническая единица:** Assured Action  
**Канонические решения:** `ACCEPT`, `REJECT`, `HOLD`

> Этот документ объединяет ключевые идеи, формулировки и инженерные решения по ProofPath из доступной истории чатов и ранее созданных материалов. Это не дословная выгрузка каждого сообщения, а очищенная каноническая версия без лишних повторов и взаимоисключающих формулировок.

---

# 0. Коротко: что такое ProofPath

> **ProofPath — это слой допуска и ответственности для AI-действий. Компания покупает не лог и не “работу узлов”, а подтверждённый допуск конкретного действия с доказательствами, независимой проверкой и заданным уровнем ответственности.**

ProofPath работает до и после значимого действия AI-агента:

```text
намерение
→ полномочия
→ policy
→ evidence
→ независимая проверка
→ ACCEPT / REJECT / HOLD
→ выполнение или блокировка
→ наблюдаемый результат
→ execution receipt
→ dispute window
```

Коммерческая единица:

> **Assured Action — завершённый проверяемый цикл действия с policy, evidence root, verdict, Clearance Certificate и Execution Receipt.**

Главная формула:

```text
Intent
+ Authority
+ Policy
+ Evidence
+ Independent Verification
+ State Binding
+ Signed Decision
+ Execution Receipt
= Assured Action
```

ProofPath не доказывает внутренние мысли модели и не обещает абсолютную безопасность.

ProofPath доказывает наблюдаемые факты:

- кто запросил действие;
- какое действие было запрошено;
- какие полномочия предъявлены;
- какая версия policy применялась;
- какие evidence проверены;
- какое состояние системы наблюдалось;
- кто участвовал в проверке;
- какой verdict получен;
- было ли действие выполнено;
- каким стало состояние после выполнения.

---

# 1. Эволюция идеи

## 1.1. Первый слой: Personal Agent Guard

Ранний продуктовый клин ProofPath — личный **Agent Seatbelt** для человека, работающего с Claude Code, Codex CLI, Cursor и похожими инструментами.

Идея:

```text
обычные действия
→ ALLOW

push / deploy / delete / migration / publish
→ ASK / HOLD / BLOCK
```

Вместо enterprise-продажи с долгими договорами пользователь получает простой личный UX:

- hook или wrapper перехватывает tool call;
- показывает действие, цель и риск;
- требует подтверждение на опасных границах;
- фиксирует approval;
- пишет audit log;
- позволяет снять понятное демонстрационное видео.

Первый технический порядок:

```text
Claude Code hooks
→ Codex CLI wrapper
→ Cursor integration
→ GitHub Action
```

Этот слой остаётся полезным как developer-led entry point, даже когда ProofPath развивается в enterprise assurance network.

---

## 1.2. Второй слой: pre-execution evidence gate

Следующая версия ProofPath стала defensive gateway:

> Любой output модели является предложением, но не авторизацией.

Канонический инвариант:

```text
agent proposal
→ authority and policy evaluation
→ ACCEPT / HOLD / BLOCK
→ side effect only after ACCEPT
→ observation separate from authorization
→ causal and replay traces
→ durable evidence
→ independent verification
```

Здесь ProofPath перестал быть просто интерфейсом подтверждения и стал проверять:

- intent;
- causal parent;
- scope;
- reversibility;
- approval lineage;
- nonce и replay;
- secrets и egress destination;
- evidence freshness;
- state binding;
- exact request digest.

---

## 1.3. Третий слой: шесть графов доверия

ProofPath развился из линейного gate в систему согласования нескольких координат действия.

Шесть графов:

1. **Intent graph** — какое намерение и кем объявлено.
2. **Authority graph** — откуда происходят полномочия и делегирование.
3. **Causal graph** — почему действие является допустимым продолжением предыдущих решений.
4. **State-transition graph** — из какого состояния в какое система должна перейти.
5. **Evidence graph** — какие доказательства подтверждают утверждения и проверки.
6. **Time / continuity graph** — актуальны ли данные, не было ли разрыва, replay или дрейфа.

Они соединяются transition cells:

```text
proposal
→ authorization
→ execution
→ observation
→ verification
```

`ACCEPT` возможен только тогда, когда координаты разрешаются согласованно.

Внутренний приоритет защитных решений:

```text
CHALLENGE
> BLOCK
> HOLD
> ACCEPT
```

Для канонического коммерческого API это нормализуется так:

- `ACCEPT` — действие соответствует условиям допуска;
- `HOLD` — требуется дополнительное evidence, approval или повторная проверка;
- `REJECT` — доказано нарушение или действие заблокировано;
- `CHALLENGE` — состояние dispute layer после выпуска решения.

Таким образом, внутренний `BLOCK` отображается наружу как `REJECT`.

---

## 1.4. Четвёртый слой: Assured Action market

Самая сильная коммерческая версия:

> **ProofPath превращает проверку AI-действий в рынок оплачиваемого доверия: компании покупают доказуемый допуск, специалисты получают деньги за независимую проверку, а ProofPath становится инфраструктурой расчётов, репутации и ответственности.**

Это уже не продажа “нод” и не ещё один security log.

Это рынок, где:

- клиент покупает Assured Action;
- witnesses получают оплату за воспроизводимую проверку;
- policy authors создают отраслевые policy packs;
- adapter developers строят коннекторы;
- challengers получают награду за доказанную ошибку;
- ProofPath получает SaaS-подписку и сетевую комиссию.

---

# 2. Проблема

Современный AI-агент может иметь действительные credentials и всё равно выполнить небезопасное действие.

Обычные системы отвечают только на части вопроса:

- IAM отвечает, к чему субъект в целом имеет доступ;
- лог отвечает, что произошло;
- sandbox ограничивает среду исполнения;
- scanner проверяет отдельный artifact;
- human approval фиксирует частное согласие;
- CI показывает статус отдельных checks.

Остаётся незакрытый вопрос уровня конкретного действия:

> Было ли это точное действие действительно намеренным, причинно авторизованным, допустимым по scope, подтверждённым актуальным evidence и безопасным для исполнения в текущем состоянии системы?

ProofPath закрывает именно этот action-level assurance gap.

---

# 3. Главное обещание

## 3.1. Для клиента

> ProofPath не позволяет AI-агенту выполнить критическое действие, пока не подтверждены полномочия, policy, evidence, актуальное состояние и требуемый уровень независимой проверки.

Клиент получает:

- policy gate;
- signed Clearance Certificate;
- объяснимый `REJECT` или `HOLD`;
- execution receipt;
- audit package;
- независимую certificate verification;
- dispute trail;
- прозрачный уровень ответственности.

## 3.2. Чего ProofPath не обещает

ProofPath не заявляет:

- что читает скрытые мысли или chain-of-thought модели;
- что любое действие безусловно безопасно;
- что transparency log делает содержание записи истинным;
- что три аккаунта автоматически означают три независимые стороны;
- что ProofPath заменяет IAM;
- что ProofPath сам предоставляет OS-level sandbox;
- что прототип равен production certification;
- что существует финансовое покрытие без лицензированного партнёра;
- что synthetic fixtures доказывают production security.

Каноническая формулировка ответственности:

> ProofPath подтверждает, что перечисленные проверки были выполнены в отношении указанного действия, политики и набора доказательств. Результат отражает соответствие заданным условиям допуска на момент проверки и не является гарантией отсутствия любого возможного ущерба.

Для версии без покрытия:

```text
VERIFIED — NOT FINANCIALLY COVERED
```

---

# 4. Главный товар: Clearance Certificate

Каждое важное действие получает сертификат.

```text
ProofPath Clearance Certificate

Action:          production deploy
Authority:       VERIFIED
Policy:          production-deploy-policy v1.0.0
Evidence:        VERIFIED
State binding:   MATCHED
Witnesses:       3 independent runtimes
Decision:        ACCEPT
Outcome:         EXECUTED
Dispute window:  24 hours
Coverage:        NOT FINANCIALLY COVERED
```

Сертификат должен отвечать:

- какое действие проверялось;
- кто запросил действие;
- какие полномочия подтверждены;
- какая policy применялась;
- какой evidence root использован;
- какое состояние было связано с решением;
- какие witnesses участвовали;
- какой quorum достигнут;
- какое решение принято;
- был ли dispatch выполнен;
- какой outcome наблюдался;
- открыт ли dispute;
- есть ли финансовое покрытие.

Сертификат и Execution Receipt — разные объекты.

- Certificate доказывает допуск и процедуру проверки.
- Receipt фиксирует факт выполнения и наблюдаемый результат.

---

# 5. MAY, DID, ASSURED

Протокол разделяет три вопроса.

## MAY — можно ли выполнять действие?

Ответ:

```text
ProofPath Permit
```

Варианты:

```text
ALLOW
DENY
CHALLENGE
```

## DID — что реально произошло?

Ответ:

```text
Outcome Record / Execution Receipt
```

Варианты:

```text
EXECUTED
BLOCKED
FAILED
TIMED_OUT
NOT_DISPATCHED
UNKNOWN
```

## ASSURED — что независимо подтверждено?

Ответ:

```text
Clearance Certificate
```

Варианты:

```text
ACCEPT
REJECT
HOLD
EXPIRED
SUPERSEDED
```

Это разделение не позволяет смешать:

- разрешение;
- факт исполнения;
- итоговый уровень доверия.

---

# 6. Три уровня решения

## ACCEPT

Выпускается, когда:

- identity подтверждена;
- authority подтверждена;
- policy однозначно идентифицирована;
- обязательный evidence присутствует;
- evidence актуален;
- request связан точным digest;
- state binding действителен;
- quorum достигнут;
- независимость достаточна;
- hard failure отсутствует.

## REJECT

Выпускается при доказанном нарушении:

- отсутствуют полномочия;
- action превышает scope;
- artifact не соответствует commit SHA;
- signature или attestation недействительна;
- request был изменён после Permit;
- nonce уже использован;
- policy запрещает действие;
- approval относится к другому environment;
- secret egress направлен неизвестному destination;
- evidence подделан.

## HOLD

Выпускается, когда безопасный ответ пока невозможен:

- evidence недостаточен;
- evidence устарел;
- state изменился после проверки;
- witnesses расходятся;
- quorum не соответствует требованиям независимости;
- требуется human approval;
- critical verifier недоступен;
- outcome не подтверждён;
- policy version конфликтует;
- действие вышло за scope, но может быть исправлено новым запросом.

Для high-risk действий содержательное расхождение witnesses приводит к `HOLD`, а не к простому большинству.

---

# 7. Уровни продукта и ответственности

## ProofPath Guard

Клиент получает:

- pre-execution policy gate;
- authority verification;
- evidence collection;
- request digest binding;
- блокировку опасных действий;
- signed decision log;
- Execution Receipt.

Доход:

- SaaS subscription;
- usage fee;
- integration fee.

## ProofPath Quorum

Дополнительно:

- curated independent witnesses;
- commitment-reveal;
- signed witness verdicts;
- diversity checks;
- Clearance Certificate;
- dispute window.

Доход:

- per-Assured-Action fee;
- network commission.

## ProofPath Bonded

Дополнительно:

- verified witness identity;
- reserve или bond;
- objective violation rules;
- challenge mechanism;
- arbitrator;
- delayed payout release.

Важно:

> Bonded не является страхованием.

## ProofPath Covered

Дополнительно:

- договор с лицензированным партнёром;
- coverage agreement ID;
- limit;
- exclusions;
- claims process;
- срок действия покрытия.

До появления такого партнёра продукт обязан использовать текст:

```text
VERIFIED — NOT FINANCIALLY COVERED
```

---

# 8. Участники экосистемы

## Requester

Человек, AI-агент, workflow или сервис, запрашивающий действие.

## Authority Provider

Источник полномочий:

- IAM;
- GitHub organization;
- corporate directory;
- approval service;
- change-management system;
- signed delegation.

## Policy Owner

Определяет:

- область действия policy;
- required evidence;
- risk thresholds;
- quorum rules;
- escalation;
- certificate TTL;
- dispute window.

## Action Gateway

Точка принудительного контроля.

Gateway обязан физически уметь не отправить действие Executor.

## Evidence Provider / Adapter

Источники:

- GitHub;
- CI/CD;
- artifact registry;
- IAM;
- cloud provider;
- vulnerability scanner;
- approval system;
- deployment controller;
- procurement;
- payment system.

## Witness

Типы:

```text
automatic witness
shadow witness
bonded witness
specialist witness
human auditor
enterprise witness
```

## Coordinator

Назначает задания и собирает commitments/reveals, но не должен иметь возможность незаметно переписать verdict.

## Executor

Выполняет действие только после независимой проверки Certificate.

## Challenger

Предоставляет проверяемое доказательство ошибки.

## Arbitrator

Рассматривает dispute и выпускает новое решение.

## Policy Author

Создаёт и поддерживает отраслевые Policy Packs.

## Adapter Developer

Строит интеграции с evidence sources и executor systems.

---

# 9. Лестница witness-допуска

```text
Shadow witness
→ Low-risk witness
→ Bonded witness
→ Specialist
→ Arbitrator
```

## Shadow witness

- выполняет контрольные задания;
- получает небольшую оплату;
- не влияет на финальный verdict;
- накапливает историю точности.

## Low-risk witness

- проверяет стандартные воспроизводимые действия;
- ограничен по риску и объёму.

## Bonded witness

- допускается к high-risk jobs;
- поддерживает reserve/bond;
- проходит identity и cluster checks.

## Specialist

- отраслевой эксперт;
- финансы, IAM, procurement, privacy, cloud security;
- получает premium.

## Arbitrator

- рассматривает споры;
- не должен быть связан с исходным quorum;
- его решение создаёт новый superseding certificate.

---

# 10. Экономика witness network

## 10.1. Не платить за согласие с большинством

Плохая модель:

```text
совпал с большинством
→ получил деньги
```

Она стимулирует копирование.

Каноническая модель:

```text
base verification fee
+ risk multiplier
+ specialization multiplier
+ SLA bonus
+ validated minority bonus
- objective violation penalty
```

Witness получает базовую выплату за:

- своевременный commitment;
- своевременный reveal;
- корректный commitment hash;
- воспроизводимые checks;
- подписанный verdict;
- отсутствие объективного нарушения.

Minority verdict сам по себе не штрафуется.

Дополнительная награда возможна, если честное меньшинство обнаружило реальную ошибку.

## 10.2. Объективные нарушения

Штраф или удержание допустимы за:

- поддельный evidence;
- двойную подпись несовместимых утверждений;
- использование чужой identity;
- доказанный сговор;
- скрытую принадлежность к запрещённому cluster;
- фиктивную проверку;
- раскрытие verdict до reveal;
- подмену implementation identity.

## 10.3. Commitment-reveal

До раскрытия ответа witness публикует:

```text
hash(
  job_id
  + witness_id
  + verdict
  + findings_digest
  + evidence_root
  + policy_digest
  + nonce
)
```

После закрытия commit-фазы публикуются:

- verdict;
- findings digest;
- evidence root;
- policy digest;
- nonce;
- signature.

Это снижает возможность дождаться чужого ответа и скопировать его.

---

# 11. Независимость witnesses

Другой GitHub-owner не обязательно означает другого человека.

Для high-risk quorum учитываются:

- KYB/KYC;
- beneficial owner;
- payment beneficiary;
- organization;
- cloud account;
- infrastructure cluster;
- verifier implementation family;
- network correlation;
- historical verdict correlation;
- conflict of interest;
- доля заданий у одного оператора.

Правила:

- не более одного witness из связанного cluster;
- разные implementation families;
- случайное или проверяемо-псевдослучайное назначение;
- лимит доли задач одному operator;
- hidden control jobs;
- повторные аудиты;
- часть выплаты в reserve до окончания dispute window.

Независимость важнее количества подписей.

---

# 12. Цена

Стартовые числа — гипотезы для пилота, а не обещание.

```text
локальная запись и подпись       $0.01–0.10
policy gate                      $0.10–1
quorum                           $1–25
критическое действие             $25–500
ручной спор / специалист         $100–2 000+
Control Cloud                    $750–5 000 / месяц
Private enterprise witness pool  $50 000–250 000 / год
14-дневный pilot                 $5 000–15 000
```

Формула цены:

```text
price =
base verification
+ number of witnesses
+ evidence complexity
+ action risk
+ urgency
+ storage
+ dispute reserve
+ optional coverage reserve
```

Пример действия стоимостью $100:

```text
$55 witnesses
$10 dispute reserve
$5  infrastructure and payouts
$30 ProofPath
```

Плюс клиентская подписка.

Клиент платит и за `REJECT`, и за `HOLD`, потому что они предотвращают ущерб и создают audit evidence.

---

# 13. Бизнес-модель

## Open core

Бесплатно:

- public schemas;
- SDK;
- CLI verifier;
- demo fixtures;
- reference Policy Pack;
- GitHub Action;
- threat model;
- non-claims documentation.

## Paid Control Cloud

Платно:

- managed policy;
- evidence ingestion;
- managed certificate service;
- witness orchestration;
- dashboards;
- audit storage;
- dispute flow;
- enterprise support.

## Revenue streams

- SaaS subscription;
- fee per Assured Action;
- paid pilot;
- enterprise integration;
- custom Policy Packs;
- private witness pools;
- specialist witness commission;
- long-term audit storage;
- compliance evidence package;
- later: licensed Covered layer.

## Не использовать

- token emission;
- mining;
- pay-to-work;
- referral pyramid;
- guaranteed yield;
- награды только из новой эмиссии;
- permissionless marketplace до product-market fit.

---

# 14. Первый рынок

## Не начинать с банковских переводов

Причины:

- высокий регуляторный порог;
- сложная ответственность;
- длинная продажа;
- сложнее доказать value быстро;
- нужен licensed coverage partner для сильных гарантий.

## Начинать с AI coding/cloud agents

Первый сценарий:

```text
AI-agent пытается:
- сделать production deploy;
- изменить IAM;
- удалить infrastructure;
- merge critical code.

ProofPath:
- проверяет authority;
- проверяет approval;
- проверяет artifact;
- связывает exact request;
- применяет policy;
- блокирует нарушение;
- выпускает signed certificate;
- отправляет high-risk случаи quorum.
```

Первый коммерческий продукт:

> **ProofPath Deployment Guard**

Покупатели:

- AI-native SaaS;
- компании, использующие coding agents;
- platform engineering;
- DevSecOps;
- regulated enterprises с AI-assisted deployment.

---

# 15. 14-дневный платный пилот

Коммерческий оффер:

> За 14 дней ProofPath подключается к одному production workflow, проверяет действия AI-агентов перед исполнением и выпускает подписанные доказательства каждого допуска, отклонения или удержания.

## Scope

```text
1 repository
1 production deployment workflow
1 target environment
1 policy pack
3 automated witnesses
100–1 000 action evaluations
```

## Обязательные результаты

- каждый deploy создаёт Action Request;
- artifact связан с commit SHA;
- authority проверяется;
- policy version фиксируется;
- выдаётся `ACCEPT`, `REJECT` или `HOLD`;
- каждый `ACCEPT` имеет Certificate;
- Executor проверяет Certificate;
- после выполнения создаётся Receipt;
- Certificate проверяется независимым CLI.

## Ключевая демонстрация

```text
unsafe request
→ artifact mismatch
→ REJECT
→ correction
→ new Action Request
→ ACCEPT
→ state verification
→ deploy
→ receipt
```

---

# 16. Минимальные fault scenarios

## Artifact mismatch

```text
commit SHA = A
artifact digest относится к commit B
```

Результат:

```text
REJECT
deployment blocked
```

## Missing approval

```text
Policy требует human approval
approval evidence отсутствует
```

Результат:

```text
HOLD или REJECT
в зависимости от policy
```

## TOCTOU / state drift

```text
pre_state_root изменился после Certificate
```

Результат:

```text
HOLD
certificate cannot be consumed
new evaluation required
```

## Дополнительные тесты

- expired Permit;
- reused nonce;
- action exceeds scope;
- approval from another environment;
- rollback policy missing;
- secret egress to unknown destination;
- witness cluster collision;
- Coordinator attempts verdict rewrite;
- tampered evidence bundle;
- request digest changed before dispatch;
- outcome missing;
- old policy bundle injected;
- path traversal in span or bundle ID;
- nonce race;
- high-risk witness disagreement.

---

# 17. Целевые метрики пилота

```text
local policy evaluation p95       < 1 sec
automated quorum p95              < 10 sec
certificate verification p95     < 500 ms
false block rate                  < 2%
evidence completeness             > 99%
certificate verification success  100%
unsafe injected actions executed  0
```

Продуктовые метрики:

- decision latency;
- evidence collection latency;
- witness response latency;
- quorum completion rate;
- HOLD rate;
- REJECT rate;
- false block rate;
- unsafe action interception rate;
- witness disagreement rate;
- manual escalation rate;
- certificate verification failures;
- challenge rate;
- successful challenge rate;
- cost per Assured Action;
- time to audit incident;
- review time saved;
- deploy acceleration.

---

# 18. Архитектура

```text
Agent / CI Workflow
        ↓
ProofPath SDK
        ↓
Evidence Collectors
        ↓
Policy Engine
        ↓
Risk Router
        ↓
Witness Coordinator
        ↓
Independent Witness Runtimes
        ↓
Decision Engine
        ↓
Certificate Service
        ↓
Deployment Gate
        ↓
Executor
        ↓
Execution Receipt
        ↓
Audit Store
```

Критические разделения:

- Policy Owner не подписывает witness verdict.
- Coordinator не может переписать verdict.
- Executor самостоятельно проверяет Certificate.
- Witness не получает право выполнить действие.
- Evidence Adapter не определяет финальное решение.
- Certificate и Receipt — разные объекты.
- Control plane signer отделён от runtime.
- Observation не заменяет authorization.
- Certificate не заменяет containment.

---

# 19. Основные протокольные объекты

## Action Request

Минимальные поля:

```text
protocol_version
action_id
created_at
expires_at
requester
actor identity
authority
scope
target
operation
request_digest
state_before_digest
risk_class
required_assurance
idempotency_key / nonce
policy reference
evidence references
```

## Evidence Object

Минимальные поля:

```text
evidence_id
type
action_id
source
subject
content_digest
issued_at
expires_at
signature
storage visibility
```

Типы evidence:

- requester identity;
- authority;
- repository identity;
- commit reference;
- artifact attestation;
- test result;
- security scan;
- human approval;
- environment state;
- policy reference.

## Policy Decision

```text
decision_id
action_id
policy_id
policy_version
policy_digest
input_digest
decision
reasons
obligations
```

## ProofPath Permit

Связывает:

- exact Action Request;
- authority digest;
- policy decision digest;
- evidence root;
- authorized request digest;
- срок действия;
- required assurance.

## Witness Commitment

```text
job_id
witness_id
commitment_hash
committed_at
```

## Witness Reveal

```text
job_id
witness_id
verdict
checks
findings_digest
evidence_root
policy_digest
nonce
signature
```

## Outcome Record

```text
outcome_id
action_id
permit_id
status
authorized_request_digest
dispatched_request_digest
state_before_digest
state_after_digest
executor_receipt_digest
response_digest
timestamps
```

## Clearance Certificate

```text
certificate_id
action_id
action summary
authority status
policy identity
evidence_root
permit_digest
outcome_digest
quorum data
decision
assurance level
coverage status
issued_at
dispute_until
supersedes
```

---

# 20. Policy Pack

Пример:

```yaml
policy_id: production-deploy-policy
version: 1.0.0

scope:
  action_types:
    - production_deploy
  environments:
    - production

required_evidence:
  - requester_identity
  - authority
  - artifact_attestation
  - test_results
  - security_scan
  - environment_state

rules:
  - id: commit_matches_artifact
    severity: critical

  - id: requester_has_prod_role
    severity: critical

  - id: required_checks_passed
    severity: critical

  - id: approval_present
    severity: high

  - id: no_critical_vulnerabilities
    severity: critical

decision:
  critical_failure: REJECT
  missing_required_evidence: HOLD
  witness_disagreement_high_risk: HOLD

quorum:
  required: true
  witnesses: 3
  threshold: 3
  diversity_clusters: 3

certificate_ttl_seconds: 900
dispute_window_hours: 24
```

Policy Pack должен иметь:

- semantic version;
- immutable digest;
- owner;
- effective date;
- scope;
- required evidence;
- decision rules;
- quorum requirements;
- certificate TTL;
- dispute window;
- post-state verification rules.

---

# 21. Репозиторий MVP

```text
proofpath/
  README.md
  LICENSE
  SECURITY.md
  CONTRIBUTING.md

  docs/
    protocol-v0.1.md
    architecture.md
    threat-model.md
    assurance-levels.md
    economics.md
    pilot.md
    non-claims.md

  schemas/
    action-request.schema.json
    evidence-object.schema.json
    policy-decision.schema.json
    permit.schema.json
    witness-commitment.schema.json
    witness-verdict.schema.json
    outcome.schema.json
    clearance-certificate.schema.json
    execution-receipt.schema.json

  packages/
    sdk/
    canonical-json/
    crypto/
    policy-engine/
    evidence-core/
    certificate-verifier/

  services/
    coordinator/
    certificate-service/
    witness-runtime-a/
    witness-runtime-b/
    witness-runtime-c/
    deployment-gate/
    audit-store/
    dispute-service/

  policies/
    production-deploy-policy/
      1.0.0.yaml

  adapters/
    github/
    sigstore/
    scitt/
    kubernetes/
    cloud/
    iam/

  cli/
    proofpath/

  examples/
    github-actions-production-deploy/

  tests/
    happy-path/
    artifact-mismatch/
    missing-approval/
    state-mismatch/
    replay/
    request-binding/
    witness-disagreement/
    cluster-collision/
```

---

# 22. API v0.1

```text
POST /v1/actions
GET  /v1/actions/{action_id}

POST /v1/actions/{action_id}/evidence
POST /v1/actions/{action_id}/evaluate
POST /v1/actions/{action_id}/permit
POST /v1/actions/{action_id}/dispatch
POST /v1/actions/{action_id}/outcome

POST /v1/witness-jobs/{job_id}/commit
POST /v1/witness-jobs/{job_id}/reveal

GET  /v1/certificates/{certificate_id}
POST /v1/certificates/{certificate_id}/verify

POST /v1/disputes
GET  /v1/disputes/{dispute_id}
POST /v1/disputes/{dispute_id}/decision
```

Пример ответа HOLD:

```json
{
  "action_id": "act_01JXYZ",
  "status": "DECIDED",
  "decision": "HOLD",
  "reasons": [
    {
      "code": "WITNESS_DISAGREEMENT",
      "message": "High-risk action did not receive unanimous quorum"
    }
  ],
  "required_next_steps": [
    "Request specialist review",
    "Refresh environment state evidence"
  ],
  "certificate_id": null
}
```

---

# 23. Canonicalization, hashing и signatures

Базовое правило:

```text
same canonical object
=
same digest
```

Рекомендуемый слой:

```text
digest = SHA-256(JCS(canonical_json))
```

Денежные значения хранятся строками, а не floating-point.

Подпись envelope должна быть адаптером, а не частью бизнес-семантики.

Поддерживаемые направления:

- Sigstore / keyless software attestations;
- in-toto statements;
- SCITT transparency receipts;
- COSE envelope;
- offline-verifiable portable evidence bundle.

Ключевое правило:

```text
canonical_payload_digest
```

должен совпадать независимо от transport/envelope.

ProofPath не должен конкурировать с форматами подписи. Его moat находится выше.

---

# 24. ProofPath moat

Не Neo4j.  
Не SHA-256.  
Не один OPA rule.  
Не ещё один log format.  
Не блокчейн ради блокчейна.

Защищаемый слой:

```text
evidence orchestration
+ enforceable policy gate
+ causal and authority binding
+ independent witness selection
+ quorum routing
+ implementation diversity
+ assurance levels
+ signed clearance
+ execution receipts
+ reputation
+ settlement
+ disputes
+ responsibility boundaries
```

---

# 25. Связка проектов

## ProofPath

Допуск внешнего действия и экономический механизм.

## CML — Causal Memory Layer

Проверяет:

- parent causes;
- ambiguous authority roots;
- broken approval lineage;
- containment;
- recovery;
- independent verification.

Роль:

```text
CML = качество поведения агента и verifier
ProofPath = разрешение внешнего действия
```

## LTP / T-Trace

Отвечает за:

- append-only transitions;
- chronology;
- parent-child links;
- replay;
- acknowledged state changes;
- transition/commit causality.

## LiminalDB

Durable replayable event-memory substrate:

- hash-linked state;
- continuity;
- durable handoff;
- replay verification.

## Ibex Agent Verification / ProofQA

Даёт:

- exact manifests;
- SHA-256 inventory;
- independent bundle verification;
- keyless Sigstore attestations;
- PASS/WARN/BLOCK release decisions;
- portable evidence bundles.

## PythiaLabs

Pre-execution decision engine:

- authorization;
- evidence freshness;
- environment;
- credentials;
- recovery context;
- ALLOW/BLOCK/ESCALATE trace.

## PoCI

Cross-graph consistency:

- согласованы ли intent, authority, cause, state, evidence и time;
- нет ли локально верных, но глобально противоречивых утверждений.

## TRACE

Метод упаковки причинности и проверяемых claims.

В будущем — научная вертикаль:

```text
Scientific Action
→ provenance
→ protocol compliance
→ independent replication
→ signed research receipt
```

## Сводная роль

```text
TIP        → какой переход оправдан
CML        → почему действие допустимо
LTP        → как путь развивался и воспроизводится
LiminalDB  → какое состояние сохранено
Ibex       → какие точные bytes и manifests доказаны
PoCI       → согласованы ли все графы
ProofPath  → можно ли выполнить действие и какой assurance выдан
```

---

# 26. Agent Action Safety Chain skill

Канонический skill ProofPath:

```text
agent-action-safety-chain
```

Основной инвариант:

```text
model output = proposal
proposal ≠ authorization
```

Operating modes:

1. Audit only.
2. Plan.
3. Implement.
4. Validate.
5. Merge — только при явном разрешении.

Обязательные проверки:

- `intent_id` существует;
- `parent_cause` существует;
- `nonce` существует и не использован;
- scope разрешён;
- irreversible/high-trust action имеет approval;
- network action проверяется по scope и destination;
- secret-bearing egress имеет допустимую lineage;
- action arguments связаны digest;
- bundle ID не может выйти за evidence root;
- unknown high-impact action fail-closed.

Минимальные negative-path tests:

- safe reversible action → `ACCEPT`;
- irreversible без approval → `HOLD`;
- missing intent → `BLOCK/REJECT`;
- missing causal parent → `BLOCK/REJECT`;
- missing nonce → `BLOCK/REJECT`;
- consumed nonce → replay block;
- secret egress unknown destination → block;
- approved allow-listed egress → accept;
- path traversal cannot escape evidence root;
- nonce race does not execute side effect;
- tampered evidence fails verification.

---

# 27. Threat model

| Угроза | Защита |
|---|---|
| Request changed after approval | exact request digest binding |
| Replay | nonce, action ID, expiry, idempotency |
| Policy rollback | signed versioned policy digest |
| Evidence tampering | content digest and issuer signature |
| Stale evidence | TTL and freshness rules |
| TOCTOU | state binding and short certificate lifetime |
| Witness copying | commitment-reveal |
| Sybil witnesses | identity, ownership, payout and cluster analysis |
| Coordinator dishonesty | signed witness records and external verification |
| Majority capture | hard-failure rules and HOLD |
| Runtime lies | independent observer and executor receipt |
| Log omission | receipts and transparency monitoring |
| Secret leakage | digest-only public records and private storage |
| Fake coverage | mandatory coverage contract reference |
| Path traversal | normalized IDs and evidence root boundary |
| Nonce race | atomic consume-before-execute |
| Policy owner conflict | role separation |
| Same verifier repeated | implementation diversity rules |

---

# 28. Dispute Protocol

## Открытие спора

Challenger предоставляет:

- certificate ID;
- disputed claim;
- evidence digest;
- описание нарушения;
- optional challenge bond.

## Evidence freeze

Фиксируются:

- Certificate;
- Witness Commitments;
- Witness Reveals;
- Policy Pack;
- Evidence Manifest;
- Outcome Record;
- Coordinator logs;
- payout state.

## Возможные решения

```text
UPHELD
AMENDED
VOIDED
INCONCLUSIVE
```

Исходный Certificate не удаляется.

Выпускается новый:

```text
new_certificate.supersedes = old_certificate
```

Стартовый reserve пилота:

```text
10%
```

Это экономический параметр, не константа протокола.

---

# 29. Definition of Done Protocol v0.1

Protocol v0.1 реализован, когда:

- есть JSON Schema для Action Request;
- есть Evidence Object;
- есть Policy Pack format;
- реализованы `ACCEPT`, `REJECT`, `HOLD`;
- реализован Permit;
- реализован commitment-reveal;
- реализован Clearance Certificate;
- существует независимый verifier CLI;
- Executor проверяет request/state binding;
- создаётся Execution Receipt;
- работает minimal dispute endpoint;
- fault scenarios проходят;
- audit package воспроизводит решение;
- CI проверяет schemas, signatures и fixtures;
- есть 90-секундная demo sequence.

---

# 30. Roadmap

## Milestone 1 — Canonical Core

- schemas;
- canonical JSON;
- hashing;
- signature abstraction;
- Action Request;
- Evidence Manifest;
- Permit;
- Outcome;
- Certificate;
- `proofpath verify`.

## Milestone 2 — Deployment Guard

- GitHub Action;
- GitHub evidence collector;
- production deploy Policy Pack;
- artifact/commit binding;
- approval checks;
- deployment gate;
- execution receipt.

## Milestone 3 — Quorum

- witness registry;
- assignment;
- independence clusters;
- commitment-reveal;
- quorum aggregation;
- signed verdicts.

## Milestone 4 — Control Cloud

- authenticated ingestion;
- policy management;
- evidence storage;
- dashboards;
- certificate registry;
- audit export.

## Milestone 5 — Economy

- operator balances;
- fiat payout;
- dispute reserve;
- challenge reward;
- reputation;
- specialist marketplace.

## Milestone 6 — Bonded and Covered

Только после реального оборота и партнёров.

---

# 31. Первые 90 дней

1. Выбрать один сценарий: production deploy.
2. Стабилизировать одну policy: `production-deploy-policy v1.0.0`.
3. Завершить schemas и offline verifier.
4. Подключить GitHub evidence collector.
5. Сделать три разные witness implementations.
6. Подключить deployment gate.
7. Выпустить Certificate и Receipt.
8. Найти 3 design partners.
9. Провести пилоты по $5 000–15 000.
10. Измерить latency, false blocks, interceptions, dispute rate и cost.
11. Выплачивать operators в обычных деньгах.
12. Не вводить token и bond до реального usage.

---

# 32. Главные риски продукта

## Слишком сложная сеть до PMF

Решение:

- curated pool;
- один use case;
- без token;
- без permissionless marketplace.

## ProofPath превращается в CI rule engine

Решение:

- independent signatures;
- portable Certificate;
- state binding;
- Execution Receipt;
- dispute;
- witness economics.

## Ложное обещание гарантии

Решение:

```text
VERIFIED — NOT FINANCIALLY COVERED
```

## Witnesses формально повторяют одну реализацию

Решение:

- implementation families;
- infrastructure diversity;
- hidden control jobs;
- CML benchmark;
- reproducible findings.

## HOLD раздражает пользователей

Решение:

- точные reason codes;
- required next steps;
- быстрый evidence refresh;
- policy-specific escalation;
- false block monitoring.

## Marketplace появляется слишком рано

Решение:

```text
internal curated pool
→ invited operators
→ enterprise private pools
→ controlled marketplace
→ broader network
```

---

# 33. Canonical pitches

## One-liner

> **ProofPath — evidence-first слой допуска для критических AI-действий: он подтверждает intent, authority, policy, state transition и result до того, как системе доверят execution.**

## Коммерческий pitch

> **ProofPath превращает проверку AI-действий в рынок оплачиваемого доверия: компании покупают доказуемый допуск, специалисты получают деньги за независимую проверку, а ProofPath становится инфраструктурой расчётов, репутации и ответственности.**

## Product pitch

> **ProofPath не позволяет AI-агенту выполнить production deploy, пока не подтверждены его полномочия, policy, artifact, обязательные approvals и актуальное состояние среды.**

## Investor pitch

> **ProofPath — assurance network for autonomous AI actions. The paid unit is an Assured Action: a signed clearance that binds declared intent, authority, policy, evidence, state and execution outcome.**

## Technical pitch

> **Treat every model output as a proposal, never as authorization. ProofPath evaluates the action before execution, binds the decision to exact evidence and state, and produces an independently verifiable receipt.**

## Strong boundary

> **Не блокчейн ради блокчейна. Не safety theater. Не попытка прочитать мысли модели. Не страховка без капитала. Сначала — проверяемый production deploy.**

---

# 34. Каноническое определение

> **ProofPath Assured Action — это криптографически связанный жизненный цикл значимого AI-действия, включающий предварительный допуск, полномочия, policy, evidence, независимую проверку, state binding, наблюдаемый outcome, уровень assurance, расчёт с operators и возможность спора.**

Главный товар клиента:

> **Не лог и не мнение аудитора, а проверяемый ответ: кто, на каком основании, по какой policy разрешил действие, что было выполнено и какие независимые стороны это подтвердили.**

---

# 35. Что делать сейчас

Канонический текущий scope:

```text
ProofPath Guard
+ Clearance Certificate
+ curated automated quorum
+ GitHub production-deploy pilot
+ offline verifier
+ Execution Receipt
```

Не расширять scope до:

- banking payments;
- open marketplace;
- token;
- financial insurance;
- medical decisions;
- universal AI safety;
- chain-of-thought proof.

Следующий инженерный порядок:

```text
schemas
→ canonicalization
→ Policy Pack
→ GitHub evidence collector
→ Permit
→ witness runtimes
→ Certificate
→ deployment gate
→ Receipt
→ verifier
→ pilot
```

---

# 36. Source index

При консолидации использованы доступные материалы и история по:

- ProofPath Master Context & Execution Plan v0.2;
- ProofPath Assured Action Protocol v0.1;
- Agent Action Safety Chain skill v1.0.0;
- PythiaLabs / Open Secure AI Alliance contribution materials;
- earlier Personal Agent Guard / Agent Seatbelt discussions;
- six-graph trust architecture discussions;
- ProofPath / CML / LTP / LiminalDB / Ibex / PoCI ecosystem mapping;
- commercial witness-network and Assured Action economics discussions;
- repository blueprint and production-deploy pilot planning.

---

# 37. Финальный принцип

```text
No evidence
→ no clearance

No authority
→ no execution

State changed
→ re-evaluate

Witnesses disagree on high risk
→ HOLD

Exact action verified
→ ACCEPT

Proven violation
→ REJECT

Every side effect
→ Receipt

Every claim
→ reproducible evidence
```
