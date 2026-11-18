# AVRORA / PsyAI Colab launcher — постоянные инструкции для агентов

## ОФИЦИАЛЬНАЯ ПРОВЕРКА GIT → COLAB И T4 18.11.2026

Прочитать **[PSYAI_COLAB_GITHUB_OFFICIAL_DEPLOYMENT_20261118.md](https://github.com/vicrex/PSYAI_PROFESSIONAL/blob/fix/psyai-case34-e2e-receipts-20261118/docs/PSYAI_COLAB_GITHUB_OFFICIAL_DEPLOYMENT_20261118.md)** до работы с Colab. Проверена официальная документация Google Colab CLI: `colab run` — штатная команда, сначала выделяет GPU, затем выполняет локальный Python-файл; альтернативный правильный маршрут для точного private Git checkout — `actions/checkout` с SSH deploy key → SHA-pinned `git archive` → `colab new -s ... --gpu T4` → `colab upload` файлов → `colab exec -f` → `colab download` → `colab stop` **только своей сессии**. Но эти изменения транспорта НЕ исправят ошибку отказа выделения GPU.

**Факты:** `44267654094` — настоящий минимальный `colab --auth=adc run --gpu T4`, **GPU allocation rejected**, до любого кода Gemma; `44277100123` — официальное read-only `colab --auth=adc sessions`, **SUCCESS: 0 активных сессий, 0 T4, 0 orphan**, без создания GPU. Старый рабочий Gemma GPU smoke `44244184390` PASS; приватный CASE34 и `git archive` PASS. **Точный механизм квоты/вместимости Google не доказан** — 412 может быть misleading `TooManyAssignmentsError` (официальный issue Google Colab CLI #73), отсутствие сессий НЕ гарантирует GPU. Текущее состояние `COLAB_T4_ASSIGNMENT_BLOCKED`, `FULL_CASE34_NOT_ACCEPTED`.

**ОСТАНОВКА ДУБЛИКАТОВ:** не запускать новые GPU-пробы, не переделывать токены/Google Drive/публичный Git, не подменять T4 на CPU под видом 10–15 минут, не объявлять полный CASE34 работающим. Проверку исходников и CLI считать завершённой, пока не изменился код. При подтверждённом доступе T4 — один штатный защищённый прогон; при отказе — документировать, не перезапускать. Режим Work не использовать в автоматизациях без прямого разрешения.


## ⛔ КАНОНИЧЕСКИЙ ПОРЯДОК CASE34: не повторять ошибочные шаги

**Единственный источник истины: [PSYAI_CASE34_CANONICAL_LAUNCH_ORDER.md](https://github.com/vicrex/PSYAI_PROFESSIONAL/blob/fix/psyai-case34-e2e-receipts-20261118/docs/PSYAI_CASE34_CANONICAL_LAUNCH_ORDER.md).** Читать его **первым**, даже если ниже есть старые сообщения «запуск готов» или «нужен Drive OAuth»: это исторические статусы. Проверка настоящего источника PASS (GitHub run **44257700183**), Gemma T4 **GPU SMOKE PASS** (run **44244184390**), Linux-совместимость PASS (run **44259843119**), статический Colab-архив PASS (run **44261083781**). Эти этапы **НЕ ПОВТОРЯТЬ**.

**Последний реальный FULL CASE34 — run 44261669852 = FAIL:** секрет и исходник с правильным SHA PASS; T4 GPU memory partition PASS; далее `PRODUCTION_DEPENDENCIES_UNAVAILABLE` за ~7 с; Gemma, E5, NLI, V2, граф, PDF/DOCX не выполнялись. Предыдущий run 44261405530 упал на Python 3.11 для `google-colab-cli==0.7.4`; исправлено на **Python 3.12**. **Привязанный к GitHub артефакту `receipt_sha256` тоже требует исправления:** bridge добавляет `colab_exit_code` после вычисления SHA — не заявлять независимую верификацию финального JSON.

**Следующий шаг СТРОГО БЕЗ GPU:** определить конкретный пакет/конфликт pip через синтетическую Linux/Python 3.12 проверку, затем исправить финальный SHA receipt и протестировать на синтетике. Только после PASS обоих gates — **один** FULL cold-run. Нет нового Google OAuth, нет переустановки Colab, нет дублирования запусков, нет EXE, нет исходника в публичном Git и нет самовольного Work. **Текущий статус: FULL_CASE34_NOT_ACCEPTED.**


## VERIFIED_CASE34_SOURCE_GATE_PASS — run 44257700183

**ИТОГ РЕАЛЬНОГО ЗАПУСКА: PASS (18.11.2026).** GitHub Actions [run 44257700183](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44257700183), `completed/success`, workflow `psyai-case34-private-source-gate.yml`, код запуска commit `2164b151bbfbe89a086d798eedc16db6f97353d9`, приватный SHA-кода тестов `af40d23f66fff39a5648589c37fd77ca5461a859`. Предыдущая попытка run `44257512252` остановилась на синтетическом тесте `bytes.replace(str)`; исправлена только ошибка теста, **реальный оригинал не менялся**.

**Контрольные доказательства (скачаны и повторно проверены независимым SHA-256):**
- GitHub Artifact `psyai-case34-private-source-gate-44257700183`, ID `14406019998`, ZIP SHA256 `3f1370944c2bae7cec2807a4e8c527f4654ac3705657cfde5423de68a77798a3`;
- `psyai-case34-private-source-proof.json`, SHA256 байт `407e7e9a72f7e6379a818bab914465be4d3f4619083101de3be0c19d1d1d5e0a`, receipt canonical SHA256 `5caf17ec424f1bb00c3e4fb3d935dc8d12d03ee152a4b8758feb9cc4d4b4b630` — независимо пересчитана, совпала;
- `status=PASS`, `reason_code=ORIGINAL_SHA_AND_ROLES_VERIFIED`, `source_verified=true`, 34 реплики, 17 client + 17 therapist, исходный SHA256 `3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc`;
- `github_encrypted_source_present=true`, `source_published=false`, `model_started=false`; синтетические safety-тесты **5/5 PASS**; приватный checkout и временные файлы удалены после проверки.

**ОБЯЗАТЕЛЬНО:** GitHub Actions encrypted secret `PSYAI_CASE34_SOURCE_B64` успешно используется для **временной** передачи CASE34 в проверенную среду; новый Google Drive OAuth НЕ НУЖЕН. Секрет НЕ удалён автоматически и должен быть удалён владельцем ПОСЛЕ настоящего полного E2E. Текущие статусы `GPU8_MODEL_PREFLIGHT_PASS_VERIFIED`, `CASE34_PRIVATE_SOURCE_VERIFIED`, `FULL_CASE34_COLAB_E2E_NOT_STARTED`. До отдельного реального E2E не объявлять анализ и цель 600–900 с пройденными. Следующий шаг — закончить Linux-совместимое приложение, E5/NLI/V2/graph и PDF/DOCX; бывшую проблему Drive/oauth не поднимать вновь.


## Verified PsyAI GPU8 llama-server baseline

**Подтверждено GitHub SUCCESS и SHA-256 receipt**, 18.11.2026:
- [Run 44244184390](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44244184390), исходный commit `57d3ac98d7916b573bcaa30d970840bf9b37746d`, `completed/success`; artifact `psyai-gpu8-colab-44244184390`, remote receipt SHA-256 `fb52b4cba4f909c388d776b29f29adeb8f7134cc89b0cf09402a4166022dc048`.
- **Единственный проверенный метод:** existing ADC + CLI 0.7.4 → pinned Gemma/llama.cpp CUDA b11774 → **llama-server localhost JSON API**, без старых `llama-cli`/`llama-completion`. Верифицированы `completion_tokens=3`, `generation_verified=true`, GPU-пик 3452 MiB ≤8192 MiB.
- **Сначала читать** [docs/PSYAI_COLAB_GPU8_RUNBOOK.md](docs/PSYAI_COLAB_GPU8_RUNBOOK.md) — вся схема, точные SHA, времена и ограничения. Не повторять GPU smoke до изменения модели или серверного кода.
- **Не путать:** GPU-smoke PASS, CASE34 full E2E **NOT STARTED**. Оригинальный диалог остаётся приватным, не отправлять его в публичные артефакты.

## PsyAI: ОБЯЗАТЕЛЬНЫЙ первый шаг
Перед поиском метода запуска, правкой скриптов или новым запуском Colab прочитать **единственный актуальный** `docs/PSYAI_COLAB_GPU8_RUNBOOK.md`. Он определяет существующий ADC, CLI 0.7.4, pinned модель и официальные CUDA binaries, точную последовательность GitHub Actions → Google Colab → SHA receipt, историю ошибок и границы полного CASE34.

Сначала смотреть последний `psyai-gpu8-colab-one-shot.yml` run и commit statuses. Если он идёт, **ничего не перезапускать**. Если упал — исправлять только доказанный этап. Для PsyAI не использовать TinyFish, сторонний браузер, новую авторизацию и параллельные прогоны. Секреты, консультации, сырые отчёты и закрытые модели не публиковать.

**GPU preflight ≠ полноценный CASE34 E2E.** Приватный E2E не объявлять выполненным без фактического SHA-bound receipt. Проверки по настоящему CASE34 должны оставаться приватными. Код AVRORA/торговля не должен запускаться через PsyAI workflow.

Этот файл и runbook задают постоянный маршрут для новых ChatGPT/Codex/Orca сессий. Не заменять его выдуманной новой схемой.
