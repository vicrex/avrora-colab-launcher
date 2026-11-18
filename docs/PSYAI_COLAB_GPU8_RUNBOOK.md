# PsyAI → Colab: ЕДИНСТВЕННЫЙ порядок запуска (18.11.2026)

## VERIFIED_CASE34_SOURCE_GATE_PASS — run 44257700183

**ИТОГ РЕАЛЬНОГО ЗАПУСКА: PASS (18.11.2026).** GitHub Actions [run 44257700183](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44257700183), `completed/success`, workflow `psyai-case34-private-source-gate.yml`, код запуска commit `2164b151bbfbe89a086d798eedc16db6f97353d9`, приватный SHA-кода тестов `af40d23f66fff39a5648589c37fd77ca5461a859`. Предыдущая попытка run `44257512252` остановилась на синтетическом тесте `bytes.replace(str)`; исправлена только ошибка теста, **реальный оригинал не менялся**.

**Контрольные доказательства (скачаны и повторно проверены независимым SHA-256):**
- GitHub Artifact `psyai-case34-private-source-gate-44257700183`, ID `14406019998`, ZIP SHA256 `3f1370944c2bae7cec2807a4e8c527f4654ac3705657cfde5423de68a77798a3`;
- `psyai-case34-private-source-proof.json`, SHA256 байт `407e7e9a72f7e6379a818bab914465be4d3f4619083101de3be0c19d1d1d5e0a`, receipt canonical SHA256 `5caf17ec424f1bb00c3e4fb3d935dc8d12d03ee152a4b8758feb9cc4d4b4b630` — независимо пересчитана, совпала;
- `status=PASS`, `reason_code=ORIGINAL_SHA_AND_ROLES_VERIFIED`, `source_verified=true`, 34 реплики, 17 client + 17 therapist, исходный SHA256 `3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc`;
- `github_encrypted_source_present=true`, `source_published=false`, `model_started=false`; синтетические safety-тесты **5/5 PASS**; приватный checkout и временные файлы удалены после проверки.

**ОБЯЗАТЕЛЬНО:** GitHub Actions encrypted secret `PSYAI_CASE34_SOURCE_B64` успешно используется для **временной** передачи CASE34 в проверенную среду; новый Google Drive OAuth НЕ НУЖЕН. Секрет НЕ удалён автоматически и должен быть удалён владельцем ПОСЛЕ настоящего полного E2E. Текущие статусы `GPU8_MODEL_PREFLIGHT_PASS_VERIFIED`, `CASE34_PRIVATE_SOURCE_VERIFIED`, `FULL_CASE34_COLAB_E2E_NOT_STARTED`. До отдельного реального E2E не объявлять анализ и цель 600–900 с пройденными. Следующий шаг — закончить Linux-совместимое приложение, E5/NLI/V2/graph и PDF/DOCX; бывшую проблему Drive/oauth не поднимать вновь.


## CASE34 — проверенный шаблон AVRORA, без нового Google Drive OAuth (18.11.2026)

**ОБНОВЛЕНИЕ МАРШРУТА:** проанализирован реально действующий `.github/workflows/avrora-private-wave.yml` и `tools/run_private_wave_checkout.py`. «Аврора» берёт код/источник из PRIVATE GitHub checkout через существующий `AVRORA_WAVE_SOURCE_DEPLOY_KEY` и использует `AVRORA_COLAB_ADC_JSON_B64` ТОЛЬКО для доступа к Colab. Google Drive для входного файла в этом пути не используется. Предыдущая попытка открыть Drive из Colab была лишней; не повторять.

**Для PsyAI уже подготовлены:** существующий приватный checkout `PSYAI_SOURCE_DEPLOY_KEY` (подтверждено run 44247014426); проверенная модель `44244184390` SUCCESS; приватный файл `tools/case34_private_secret_preflight.py` + регрессионные тесты `tests/test_case34_private_secret_preflight.py`; отдельный подготовленный мануальный `.github/workflows/psyai-case34-private-source-gate.yml` (без GPU). Последний pinned-private source SHA `ecd19958919541d5985a86c66152c0b880ac0c82`, public workflow SHA `8e38c22ed564c6d31b0cd5e2e390e21f912007bd`.

**Одна недостающая операция владельца:** положить исходные байты **в GitHub Actions encrypted secret**, а не в git-историю или Google Drive OAuth: `PSYAI_CASE34_SOURCE_B64` в репозитории `vicrex/avrora-colab-launcher`. Уже подготовлен приватный PowerShell installer `vicrex/PSYAI_PROFESSIONAL` → `tools/install_case34_source_secret.ps1` (SHA-256 оригинала до передачи, GitHub CLI owner check, секрет через stdin, не через argv или git). Требует `gh` и локально доступный оригинальный CASE34; никакой новый Google доступ и сборка EXE не требуются. Прозрачная граница доверия: пользователи с правом редактировать Actions этого репозитория потенциально могут получить доступ к секретам; после завершения полного CASE34 владелец удаляет секрет командой скрипта `-DeleteAfterCompletedCase34`.

**Точный порядок:** 1) проверить исходный SHA-256 и 34 роли локально; 2) **одна** установка encrypted secret владельцем; 3) **один** `workflow_dispatch` существующего `PsyAI CASE34 secure source readiness (NO GPU)`, никаких `push` автозапусков; 4) проверить `source_verified=true`, `turns=34`, `source_published=false`, receipt digest и отчет без диалога; 5) **только после этого** подготавливать/исполнять отдельный реальный Linux E2E Gemma + E5 + graph + NLI/V2 + PDF/DOCX; 6) после успешной приёмки удалить временный secret. **GPU smoke не повторять**.

**ТЕКУЩИЙ ЧЕСТНЫЙ СТАТУС:** `GPU8_VERIFIED_SUCCESS`, `CASE34_ORIGINAL_SHA_LOCAL_PASS`, `PRIVATE_SOURCE_SECRET_NOT_INSTALLED_OR_NOT_VERIFIED`, `FULL_CASE34_NOT_STARTED`. Код preflight/доставка подготовлен, но secret НЕ установлен через доступные инструменты и запуск CASE34 не сделан. Нельзя выдавать изменения в git за запуск Gemma.

**Не использовать устаревший отдельный `drive.readonly` OAuth путь**, не запрашивать новую авторизацию Google; он остался альтернативным исследованием и НЕ требуется по схеме AVRORA. Никогда не передавать реальный исходник в публичные git-файлы, URL, stdout/stderr, Actions artifacts или отчёты.


## CASE34 PRIVATE SOURCE READINESS — verified scope blocker

**Не переизобретать проверку и не запускать модель:** отдельный read-only, NO-GPU workflow уже реализован — `.github/workflows/psyai-case34-private-source-gate.yml`, а приватный helper — `vicrex/PSYAI_PROFESSIONAL` → `tools/case34_private_drive_preflight.py`. Источники в публичный launcher/артефакты не передаются.

**Контрольные запуски:**
- Run [44246391842](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44246391842) = `completed/failure`, `BLOCKED_EXISTING_PRIVATE_DRIVE_ADC_NOT_PRESENT`: отсутствует отдельный `AVRORA_PRIVATE_DRIVE_ADC_JSON_B64`. Проверка наличия приватного GitHub deploy key прошла.
- Run **[44247014426](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44247014426)** = `completed/failure`, код commit `53653e734aadc98cfd4ac97a210cf87d05c49e25`. Вторая проверка без GPU протестировала **уже существующий Colab ADC** как запасной вариант, *без запроса нового OAuth scope*: `PRIVATE_DRIVE_SCOPE_NOT_PREGRANTED`. Приватный checkout, статическая проверка скрипта и наличие Colab ADC прошли. Артефакт `psyai-case34-readonly-gate-44247014426`, ID `14401469693`, SHA-256 ZIP `3ffd736d08da4f20c1e965ad6821a9fc6ec3ff522abcab5c499104c8543f1a99`. Внутренний receipt hash независимо пересчитан — совпал; `model_started=false`, `source_uploaded=false`.
- Оригинальный приватный файл отдельно прочитан **через уже подключённый Google Drive в сессии владельца**, подтверждены объём, SHA и роли 34 реплик. Это **не** доказывает, что Colab уже имеет право его прочитать.

**Проверенная причина остановки:** недостаёт **одного** разрешённого механизма чтения закрытого Google Drive в изолированном GitHub Actions/Colab. Штатный `AVRORA_COLAB_ADC_JSON_B64` не имеет Drive scope; `AVRORA_PRIVATE_DRIVE_ADC_JSON_B64` отсутствует. Нельзя самовольно расширять scopes, публиковать диалог, делать link sharing, вставлять transcript в публичный репозиторий или GitHub workflow args. Успешная модельная GPU8-контрольная проверка `44244184390` остаётся **PASS**, повторять её НЕ НУЖНО.

**Единственный следующий технический gate:** владелец должен один раз одобрить безопасное Drive чтение (существующий инструмент настройки `tools/connect_private_drive_cloud_shell.sh` + `tools/verify_private_drive_adc.py`; сохранять OAuth JSON **только через защищённый GitHub secret** `AVRORA_PRIVATE_DRIVE_ADC_JSON_B64`, не в чат/коммит/логи). Этот прежний инструмент даёт полномасштабный scope `drive`, поэтому пользователь должен знать границу прав доступа и при желании использовать отдельную учётную запись. После настройки — один ручной `workflow_dispatch` уже готового `psyai-case34-private-source-gate.yml`; проверять `source_verified=true`, настоящий SHA/17+17 и `source_uploaded=false`. До PASS НЕ запускать платный/тяжёлый Colab CASE34.

**Статусы:** `GPU8_BASELINE_VERIFIED`, `CASE34_ORIGINAL_BYTES_VERIFIED_LOCALLY`, `CASE34_PRIVATE_DRIVE_OAUTH_MISSING`, `FULL_CASE34_E2E_NOT_STARTED`.


## ✅ VERIFIED_GPU8_SERVER_BASELINE — 18.11.2026

**СТАТУС: ПРОВЕРЕНО ПОВТОРНЫМ ЧТЕНИЕМ GITHUB + АРТЕФАКТА.** Это **один GPU-smoke**, а не полный CASE34.

- GitHub Actions **[Run 44244184390](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44244184390)**: `completed/success`, job `134598998804`: `success`. Git commit **`57d3ac98d7916b573bcaa30d970840bf9b37746d`**, script revision `57d3ac98d791`.
- Получен `psyai-gpu8-colab-44244184390` (artifact ID **14400829035**, ZIP digest `sha256:10efe6e19eaf1d13a8505563d731407e0517d4858c896c559be71aa66bb2e4f2`). JSON из ZIP проверен повторным вычислением SHA-256 canonical JSON: `fb52b4cba4f909c388d776b29f29adeb8f7134cc89b0cf09402a4166022dc048` — **совпал**.
- `status=GPU8_MODEL_PREFLIGHT_PASS`, `generation_verified=true`, `case34_full_e2e=false`, `cli_exit_code=0`, `journal.final_status_published=true`, 21/21 commit statuses записаны без ошибок.
- T4 **15360 MiB физически**, после резервирования избыточной памяти доступно **7946 MiB** при целевом лимите **8192 MiB**; реальный GPU-пик `llama-server` — **3452 MiB**.
- Модель `google/gemma-4-12B-it-qat-q4_0-gguf`, revision `ef7b15515d7ed7f34305a08edb5717e7989d6dc9`, GGUF `gemma-4-12b-it-qat-q4_0.gguf`, SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b` — сверено на удалённом Colab.
- Официальные предварительно собранные CUDA-бинарники llama.cpp release `b11774` (два проверяемых SHA-256 — ниже); не компилировать `llama.cpp`. **Исправление, давшее PASS**: вместо `llama-cli`/`llama-completion` использовать `llama-server` на `127.0.0.1` → `GET /health` → `GET /v1/models` → `POST /v1/chat/completions` (`stream=false`, `max_tokens=96`, `temperature=0`, `reasoning_effort=none`, `enable_thinking=false`). Результат сверять по `choices[0].message.content` и `usage.completion_tokens`, а **не по консольному stdout**.
- **Доказательство ответа:** `completion_tokens=3`, `content_chars=10`, `finish_reason=stop`, `recognized_canary=true`, `reply_schema=true`, `reasoning_only=false`. Вывод модели не сохранялся в публичный GitHub.
- **Замеры:** загрузка модели 124.78 с, её SHA-проверка 41.28 с, `server_ready_seconds=114.65`, `inference_seconds=57.59`, CUDA подготовлена к 215.82 с от старта, `gpu8_inference` 388.06 с от старта, полный Colab `elapsed_seconds=391.49` с, общий GitHub bridge `399.07` с.
- **Постоянный маршрут:** GitHub Actions `.github/workflows/psyai-gpu8-colab-one-shot.yml` → existing `AVRORA_COLAB_ADC_JSON_B64` → `google-colab-cli==0.7.4` → `tools/psyai_gpu8_colab_bridge.py` → `tools/psyai_case34_gpu8_colab_probe.py` → JSON `psyai_gpu8_proof.json`. Сначала смотреть последний run/status и этот pinned-good commit; не открывать браузер, не требовать повторной авторизации, не создавать другие launcher и не делать новые cold-runs без изменения модели/сервера.
- **ОБЯЗАТЕЛЬНАЯ ГРАНИЦА:** полный разбор CASE34, E5+NLI+V2+граф, PDF/DOCX и цель 600–900 с **не проверены этим smoke**. Для них нужен отдельный закрытый Linux-совместимый E2E с защищённым источником. `FULL_CASE34_COLAB_NOT_READY` остаётся актуальным до его отдельного фактического прогона.

**Последующие исторические FAIL-разделы ниже описывают УСТРАНЁННЫЕ дефекты старых запусков; они не отменяют подтверждённый SUCCESS выше.** Не менять рабочие pinned версии ради косметики.


**Источник истины для следующей сессии/агента.** Перед ЛЮБЫМ изменением или запуском PsyAI через Colab читать этот файл. Не создавать новый launcher, новую авторизацию, платный браузер или параллельный GPU run.

## 1. Что уже создано и подтверждено

- **Launcher:** `vicrex/avrora-colab-launcher`, ветка `main`, workflow `.github/workflows/psyai-gpu8-colab-one-shot.yml`. Приватный код: `vicrex/PSYAI_PROFESSIONAL`, ветка `fix/psyai-case34-e2e-receipts-20261118`.
- **Авторизация Google Colab:** существующий GitHub Actions secret **только по имени** `AVRORA_COLAB_ADC_JSON_B64`. Google Colab CLI строго `google-colab-cli==0.7.4`. Не читать/копировать/обновлять секрет, не запускать веб-авторизацию. Для запуска: `colab --auth=adc run --gpu T4 --timeout 2100 tools/psyai_case34_gpu8_colab_probe.py` через bridge, **не вручную поверх действующего run**.
- **Запуск:** `tools/psyai_gpu8_colab_bridge.py` → `tools/psyai_case34_gpu8_colab_probe.py`. Bridge: heartbeat раз в 60 с и `psyai-gpu8/stage/*` в commit statuses, внешнее ожидание 40 мин, защищённый `psyai_gpu8_proof.json`; workflow: 45-минутный шаг и максимум 85 мин на job, single-run concurrency `psyai-colab-cpu-global-nonparallel`.
- **Модель:** `google/gemma-4-12B-it-qat-q4_0-gguf`, revision `ef7b15515d7ed7f34305a08edb5717e7989d6dc9`, файл `gemma-4-12b-it-qat-q4_0.gguf`, SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`.
- **CUDA бинарники без компиляции:** официальный `ggml-org/llama.cpp`, релиз `b11774`, `llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz` SHA-256 `7d03c8482b62c9533d47e777c0d3ca2edce6e57916b51f587a4576d332757fbb`, `cudart-llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz` SHA-256 `d4fe9a68a521add2001396fdc324dcc613104a2e7a175b68823448793bf8eb9f`. Скачать, сверить SHA, распаковать во временную Colab папку; загрузка CUDA должна пройти тест, наличие tarball не означает успех. **Никогда вновь не компилировать mutable upstream/main для GPU8 preflight без отдельного обоснования.**
- **GPU:** NVIDIA T4, резервировать лишнюю память PyTorch, доступный бюджет ≤8192 MiB, контролировать PID реальной модели и свободную память. `-ngl 20 -c 2048 -b 256 -ub 128 -n 32`; проверочная генерация `маяк`. T4 с таким ограничением — тест бюджета VRAM, **не точная эмуляция RTX 4060**.
- **Приватный CASE34:** оригинал находится в закрытом Google Drive владельца. Точный идентификатор и SHA-256 хранятся только в приватном `vicrex/PSYAI_PROFESSIONAL` → `AGENTS.md` и `docs/CASE34_ONE_SHOT_RUNBOOK_20261118.md`. Не публиковать имена, идентификаторы файлов консультаций, полный текст или его хеш в публичном launcher. Узкий ADC для Colab **не обеспечивает доступ к Drive**.
- **Важно:** `psyai-gpu8-colab-one-shot.yml` выполняет только GPU preflight, **не** CASE34. `psyai-private-colab-acceptance.yml` читает приватную рабочую ветку и проверяет CPU на синтетических данных, тоже **не** CASE34. Исходный `tools/run_case34_hybrid_acceptance.py` вместе с `tools/e2e_full_gemma.py` используют Windows API (EXE, taskkill/реестр) и НЕ запускаются на Colab Linux без адаптации.

## 2. Алгоритм запуска — нельзя пропускать шаги

1. **Сначала существующие процессы.** Читать `https://github.com/vicrex/avrora-colab-launcher/actions` и последний run GPU8; проверить `status`, `conclusion`, job steps. Для долго работающего bridge читать commit statuses по SHA запуска: `GET /repos/vicrex/avrora-colab-launcher/commits/<HEAD_SHA>/status`, контексты `psyai-gpu8/heartbeat` и `psyai-gpu8/stage/*`. `waiting_for_colab_output` подтверждает только bridge, не GPU. При `in_progress` **не создавать новый run, не отменять его автоматически**.
2. **Диагноз по этапу.** `GPU8_MODEL_PREFLIGHT_PASS` только если фактический удалённый receipt проверен SHA и содержит T4, точный SHA модели, успешную генерацию и измеренный пик памяти ≤8192 MiB. Если один этап упал, изменять только его, не перестраивать всё и не повторять тяжёлый cold-run без причины. `404 BlobNotFound` логов Actions — проблема получения логов, проверять отдельные commit statuses.
3. **Прежде чем запускать:** сверить HEAD точных файлов workflow, bridge, probe и этой инструкции. Статически проверить `python -m py_compile tools/psyai_case34_gpu8_colab_probe.py tools/psyai_gpu8_colab_bridge.py tools/psyai_gpu8_status.py`, совпадение CUDA asset SHA, доступность `--gpu`/`--timeout` в CLI 0.7.4. Никаких секретов и пациентских данных в git, stderr, артефактах.
4. **Один запуск:** открыть GitHub Actions → `PsyAI Gemma 4 12B T4 GPU 8GiB one-shot preflight` → `Run workflow` → `main`, или операторский `gh workflow run psyai-gpu8-colab-one-shot.yml -R vicrex/avrora-colab-launcher --ref main`. В скрипте нельзя переиспользовать старые/параллельные Colab-сессии. `workflow_dispatch` уже есть; само наличие файла в GitHub НЕ значит, что запуск сделан.
5. **Доказать запуск:** записать фактические `run_id`, `head_sha`, `job_id`, `status`, этапы `START/PASS/FAIL/TIMEOUT/BLOCKED`, receipt SHA-256, время model download, CUDA archive download, inference, peak VRAM. После `completed` сверить `conclusion` и `psyai_gpu8_proof.json`; если не проверено, статус `BLOCKED/INCOMPLETE`, а не PASS.
6. **Cleanup:** только свой временный Colab runtime, только свои временные файлы/секреты в Actions, без изменения настроек или данных AVRORA. Никакой EXE сборки, Bybit, торговых сценариев и передачи консультаций в публичный launcher.

## 3. История конкретных ошибок — не повторять

| Run | Подтверждённый исход | Причина / урок |
| --- | --- | --- |
| `44232378197` | FAIL, без remote receipt | CLI завершился слишком рано; причина 30-секундного таймаута не доказана. |
| `44233223824` | FAIL до GPU | Неверный тест строки `--gpu` в stdout `--help`; заменено проверкой API CLI. |
| **`44233640763`** | **FAIL** | T4/8GiB/Gemma SHA PASS, компиляция CUDA `TIMEOUT` после 1500 с. Заменена официальными CUDA бинарниками. |
| **`44238014973`** | **FAIL** | T4/8GiB/Gemma SHA/официальные CUDA бинарники PASS. `cuda_llama_binary` прошло за 148 с с начала; `model_inference` завершился без распознанного русского `маяк`: `NO_GENERATED_CANARY`, GPU stage stopped на 382 с. **Это не доказательство отсутствия всех токенов**, так как ответ мог быть на английском; stdout не сохранялся. Добавлен fail-closed русский/английский canary+обезличенная диагностика. |
| **`44239143245`** | **FAIL** | Сверен полный SHA-проверенный proof: T4 PASS, Gemma SHA PASS, CUDA binaries PASS (138.95 с от старта), GPU-пик процесса **3456 MiB** при лимите 8192. `llama-cli` вышел с кодом 0, но stdout **3558 байт**, `canary_ru=false`, `canary_en=false`, `has_llama_timing=false`; `NO_RECOGNIZED_GENERATED_CANARY`. **Нельзя считать реальную генерацию подтверждённой**. Вероятный транспортный дефект CLI в non-TTY, подтверждённый официальным issue llama.cpp №27214. Следующий адресный фикс — `llama-completion --jinja --single-turn --simple-io`. |

**Запрет:** не утверждать «запущен CASE34», когда выполняется только GPU preflight или меняются файлы. Не утверждать «новый GPU тест PASS», пока нет проверенной remote receipt.

## 4. Что нужно именно для ПОЛНОГО CASE34 (отдельная задача)

1. Проверенный приватный источник: оригинальный CASE34 из закрытого Drive, локально сверить байтовый SHA, 34 реплики (17+17), не публиковать полный текст, промпты и сырые результаты в открытом GitHub/логах.
2. Закрытый канал доступа к оригиналу с явным соответствующим разрешением. **Не** предполагать, что существующий `AVRORA_COLAB_ADC_JSON_B64` умеет Drive API. Нужен уже разрешённый закрытый путь либо отдельный согласованный доступ — без запросов избыточных scopes.
3. Linux-совместимый end-to-end PsyAI (не Windows `taskkill`/`llama-server.exe`), зафиксированная версия Python/Gemma/E5/NLI, однократное выполнение, fail-closed V2 для claims и edges, верное авторство, гипотезы и альтернативы.
4. Выдать только безопасную агрегированную receipt: sha источника, code SHA, model SHA, времена каждого этапа и общего анализа, граф V2, проверки ложных `SUPPORTED`, статус PDF/DOCX. Полный текст и отчёты только в закрытом хранилище. Цель **600–900 с** измеряется реальным CASE34, не тестовой генерацией.
5. Пока пункты 2–4 не реализованы и не проверены, `FULL_CASE34_COLAB_NOT_READY` — это точный статус, а не «идёт».

## 5. Точка возврата в будущей беседе

**Начинать здесь:** читать данный runbook → GitHub Actions GPU8 latest run → commit-status stages → один адресный фикс/контрольный запуск (если нужно) → только затем отдельный приватный CASE34. Правила также продублированы ссылкой в `vicrex/PSYAI_PROFESSIONAL` → `AGENTS.md`. Не запускать TinyFish, не пытаться использовать браузерный сервис с отдельным балансом и не заказывать новую Google авторизацию.


## 6. Проверка каждого нового исправления — обязательна

- **До запуска:** readback-коммит каждого изменённого файла; быстрый `python -m py_compile` и проверка функций на искусственных ответах **без доступа к GPU**. Никаких тяжелых повторов ради проверки только синтаксиса.
- После `44238014973` введён `recognize_generated_canary(output)`: нормализация UTF-8/Unicode, допускает корректное русское «маяк» и английское «lighthouse»/«beacon», но не считает пустой вывод или только текст логов генерацией. Никакие приватные ответы/промпты не попадают в receipt; только длина, SHA-префикс, флаги совпадения, наличие timing.
- **Следующий единичный запуск** может подтвердить или опровергнуть гипотезу об английском ответе. Если опять `NO_RECOGNIZED_GENERATED_CANARY`, сначала анализировать `inference_output_probe` из sanitized `psyai_gpu8_proof.json` (в первую очередь `stdout_bytes`, `stdout_nonspace_chars`, `has_llama_timing`, `canary_ru/en`), а не бесконечно перезапускать.
- `completed/failure` в GitHub всегда важнее предварительных `PASS` отдельных стадий. Отсутствие finale `GPU8_MODEL_PREFLIGHT_PASS` означает **непринятый** тест.
- **Полный CASE34:** только отдельно после достигнутого и документированного GPU8 preflight. Тяжёлый GPU тест `маяк` не подтверждает психологический анализ, 600–900 секунд или качество E5/NLI/V2.


## 7. Важная ловушка автозапуска при push

**Проверено по run `44239143245`:** `.github/workflows/psyai-gpu8-colab-one-shot.yml` слушает не только `workflow_dispatch`, но также `push` в:
- `.github/workflows/psyai-gpu8-colab-one-shot.yml`;
- `tools/psyai_case34_gpu8_colab_probe.py`;
- `tools/psyai_gpu8_colab_bridge.py`;
- `tools/psyai_gpu8_status.py`.

**Следствие:** сохранение исправления в любой из этих четырёх файлов уже запускает один новый GPU workflow **автоматически**. Не добавлять следом «ручной» run, не менять их ещё раз во время `in_progress`, иначе concurrency `cancel-in-progress: true` может отменить реальную Colab-сессию. Инициатор запуска после push — GitHub Actions, а не отдельный ручной Colab вызов.

Сначала `push/readback` одного адресного изменения → проверка автоматически созданного `run_id` → стадии/receipt → только после завершения следующий шаг. Если нужны изменения инструкции без запуска, изменять исключительно `docs/` или `AGENTS.md` (они не входят в trigger paths). Руководствоваться фактическим последним workflow-файлом, а не предположением, что `push` не запускает тест.

Запуск `44239143245` создан именно на `push` исправленного canary-проверяющего скрипта (`89465ab17f2f`). Он не подтверждает полный CASE34. После завершения записать здесь конкретный этап, outcome и причину ошибки.


## 8. Зафиксированная причина неинтерактивного CLI (после 44239143245)

- Публичный GPU-скрипт запускает `llama-cli` с `stdout=PIPE`, `stderr=STDOUT` и `-p`. По подтверждённому issue **ggml-org/llama.cpp #27214** (https://github.com/ggml-org/llama.cpp/issues/27214) `llama-cli` в Linux при перенаправленном stdin/stdout может завершиться с кодом 0 без нормального ответа; режим разговора может не завершиться при `-no-cnv`.
- Официальная документация `tools/completion/README.md` (https://github.com/ggml-org/llama.cpp/blob/master/tools/completion/README.md) даёт *one-and-done* `llama-completion`, а с Jinja — `--jinja --single-turn -p`; `--simple-io` предназначен для подпроцессов.
- Установленная причина **не** доказана исключительно последним журналом: подтверждено, что прежняя процедура **не дала** проверяемого ответа, несмотря на код 0 и реальное использование GPU. Это достаточный повод для адресной замены CLI без переустановки Colab и модели.
- **Контрольный запуск допускается только один**, после проверки `py_compile`, положительных/отрицательных тестов канарейки и структуры CLI-аргументов. Замена `llama-cli` на `llama-completion` и одна транзакционная правка кода/workflow в **одном Git-коммите** (workflow запускается от `push` ровно один раз); затем readback run ID, stages и SHA receipt. Если снова FAIL — **НЕ перезапускать** до анализа нового receipt.
- После `GPU8_MODEL_PREFLIGHT_PASS` переход к отдельной приватной приёмке CASE34; использование `llama-completion` в canary никак не заменяет настоящую E/S/V2 архитектуру PsyAI.


## 9. Финал запуска llama-completion и СТОП повторным cold-run

**Проверено 18.11.2026, новый Run [44240472635](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44240472635), SHA `17b240e601fdf354842bb5dd465ed2ba57501aef`:**

| Критерий | Подтверждённые данные |
| --- | --- |
| Github Actions | `completed / failure` |
| Статический валидатор Python и негативные тесты ответа | PASS |
| Colab GPU | Tesla T4, резерв до 8192 MiB PASS |
| GGUF Gemma 4 12B | SHA-256 PASS |
| CUDA | Official release `b11774`, `cuda_llama_binary` PASS |
| Реальная GPU память процесса | пик 3534 MiB |
| Новый транспорт | `llama-completion --jinja --single-turn --simple-io` |
| Результат | `NO_RECOGNIZED_GENERATED_CANARY`, `generation_verified=false`, FAIL |
| stdout (только агрегаты, **не сырой ответ**) | 3217 байт / 2549 непробельных символов, `has_llama_timing=true`, русский и английский canary — `false` |
| Время | remote 438.25 с, GitHub bridge 458.41 с |
| Подтверждение | SHA remote receipt `9c8b08ac112dca4eefbbc4564b6b123f32d205f9e3ccd5760f513a0adb049946`, GitHub artifact `psyai-gpu8-colab-44240472635` |

**Решение:** `STOP_DUPLICATE_GPU8_CANARY`. Нельзя снова запускать исходную проверку `maяк` с тем же интерфейсом и надеяться на иной результат. Доказана работоспособность входа в Colab, загрузки модели, CUDA, GPU-выделения; **не доказана полезная генерация**. Exit code 0 и GPU-pid сами по себе её не подтверждают.

**ИСТОРИЧЕСКАЯ ЗАПИСЬ ДО УСПЕХА; УЖЕ РЕАЛИЗОВАНО И PASS В RUN 44244184390:** использовать тот же SHA-pinned готовый `llama-server` из релиза `b11774`, localhost `127.0.0.1`, запрос `POST /v1/chat/completions` с коротким **синтетическим** промптом; проверять **JSON** `choices[].message.content` и `usage.completion_tokens` отдельно от stderr/stdout сервера. Официальная документация: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md . Сервер — тот же тип runtime, который использует PsyAI. Перед выделением GPU тестировать парсер JSON и таймауты **без модели**; только после проверенного patch+difference, отдельного подтверждения отсутствия текущего run и одноразовой принятой командной процедуры допустим следующий холодный тест.

**Границы:** отдельный `CASE34_FULL_E2E` сейчас `NOT_STARTED`; модельная canary-проверка и PDF/DOCX не проведены. Приватный оригинал остаётся в закрытом Drive. Установленный ADC Colab не обеспечивает Drive scope; не нарушать эту границу.


## 10. Серверный JSON-прогон: зафиксированный протокол

**Реально выполнен и подтверждён SUCCESS контрольный run [44244184390](https://github.com/vicrex/avrora-colab-launcher/actions/runs/44244184390) по атомарному коммиту `57d3ac98d7916b573bcaa30d970840bf9b37746d`.** Он использует уже существующий `AVRORA_COLAB_ADC_JSON_B64` и `google-colab-cli==0.7.4`. Итог после завершения: **completed/success**, SHA-bound receipt подтверждён (см. VERIFIED_GPU8_SERVER_BASELINE выше).

Проверка выполняется из действующего workflow `.github/workflows/psyai-gpu8-colab-one-shot.yml` и `tools/psyai_case34_gpu8_colab_probe.py`: Colab T4 → резерв VRAM ≤8192 МиБ → SHA-256 pinned Gemma GGUF → два официальных SHA-проверенных CUDA-архива `llama.cpp b11774` → локальный `llama-server` на `127.0.0.1:<случайный свободный порт>` → готовность `/health` → `GET /v1/models` → **`POST /v1/chat/completions`**, `stream=false`, `temperature=0`, `max_tokens=96`, `reasoning_effort=none`, `chat_template_kwargs.enable_thinking=false`. Контрольный вопрос синтетический, не содержит ожидаемого ответа. Отдельно проверяются поле `choices[0].message.content`, `usage.completion_tokens>0`, правильный ответ (`lighthouse`/«маяк»), пик процесса ≤8192 МиБ. Никакие сырые ответы, токены доступа или данные консультаций не публикуются.

**Критерии принятия:**
1. GitHub `status=completed`, `conclusion=success`; все необходимые стадии (включая `server_ready`, `gpu8_inference`) `PASS`.
2. Получен один `PSYAI_GPU8_COLAB_RECEIPT` с корректным SHA-256, `status=GPU8_MODEL_PREFLIGHT_PASS`, `generation_verified=true`, измерены `completion_tokens>0`, пик GPU ≤8192 МиБ. Совпадение слова в логах и код процесса 0 **не являются** доказательством.
3. Artifact `psyai-gpu8-colab-<run_id>` проверен; сопоставлены commit SHA, времена и результат. При провале записать конкретный `failure_code`, не называть PASS и **не повторять запуск без адресного исправления**.
4. Если всё прошло, закрепить здесь точные `run_id`, полный commit SHA, digest receipt, параметры CLI/server, модель/ревизию/SHA, CUDA версии/дижесты, VRAM, времена, ссылки на реальный artifact; пометить этот маршрут **VERIFIED_GPU8_SERVER_BASELINE**. Ту же ссылку и статус внести в приватный `vicrex/PSYAI_PROFESSIONAL` → `AGENTS.md` и `docs/PSYAI_COLAB_STATUS_20261118.md`. Обе записи сверить чтением из GitHub после коммита.
5. После такого PASS новые проверки GPU запускаются **только при изменении модели, бинарников, ресурсов или серверного кода**. Полный CASE34 остаётся отдельной приватной проверкой: не выдавать GPU canary за E2E анализа.

**Автозапуск:** правки `tools/psyai_case34_gpu8_colab_probe.py`, `tools/psyai_gpu8_colab_bridge.py`, `tools/psyai_gpu8_status.py` или самого workflow запускают новый Colab-run через GitHub `push`; **документы `docs/` и `AGENTS.md` не запускают GPU**. Во время текущего запуска менять только документы.
