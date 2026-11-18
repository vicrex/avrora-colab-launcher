# PsyAI → Colab: ЕДИНСТВЕННЫЙ порядок запуска (18.11.2026)

**Источник истины для следующей сессии/агента.** Перед ЛЮБЫМ изменением или запуском PsyAI через Colab читать этот файл. Не создавать новый launcher, новую авторизацию, платный браузер или параллельный GPU run.

## 1. Что уже создано и подтверждено

- **Launcher:** `vicrex/avrora-colab-launcher`, ветка `main`, workflow `.github/workflows/psyai-gpu8-colab-one-shot.yml`. Приватный код: `vicrex/PSYAI_PROFESSIONAL`, ветка `fix/psyai-case34-e2e-receipts-20261118`.
- **Авторизация Google Colab:** существующий GitHub Actions secret **только по имени** `AVRORA_COLAB_ADC_JSON_B64`. Google Colab CLI строго `google-colab-cli==0.7.4`. Не читать/копировать/обновлять секрет, не запускать веб-авторизацию. Для запуска: `colab --auth=adc run --gpu T4 --timeout 2100 tools/psyai_case34_gpu8_colab_probe.py` через bridge, **не вручную поверх действующего run**.
- **Запуск:** `tools/psyai_gpu8_colab_bridge.py` → `tools/psyai_case34_gpu8_colab_probe.py`. Bridge: heartbeat раз в 60 с и `psyai-gpu8/stage/*` в commit statuses, внешнее ожидание 40 мин, защищённый `psyai_gpu8_proof.json`; workflow: 45-минутный шаг и максимум 85 мин на job, single-run concurrency `psyai-colab-cpu-global-nonparallel`.
- **Модель:** `google/gemma-4-12B-it-qat-q4_0-gguf`, revision `ef7b15515d7ed7f34305a08edb5717e7989d6dc9`, файл `gemma-4-12b-it-qat-q4_0.gguf`, SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`.
- **CUDA бинарники без компиляции:** официальный `ggml-org/llama.cpp`, релиз `b11774`, `llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz` SHA-256 `7d03c8482b62c9533d47e777c0d3ca2edce6e57916b51f587a4576d332757fbb`, `cudart-llama-b11774-bin-ubuntu-cuda-12.8-x64.tar.gz` SHA-256 `d4fe9a68a521add2001396fdc324dcc613104a2e7a175b68823448793bf8eb9f`. Скачать, сверить SHA, распаковать во временную Colab папку; загрузка CUDA должна пройти тест, наличие tarball не означает успех. **Никогда вновь не компилировать mutable upstream/main для GPU8 preflight без отдельного обоснования.**
- **GPU:** NVIDIA T4, резервировать лишнюю память PyTorch, доступный бюджет ≤8192 MiB, контролировать PID реальной модели и свободную память. `-ngl 20 -c 2048 -b 256 -ub 128 -n 32`; проверочная генерация `маяк`. T4 с таким ограничением — тест бюджета VRAM, **не точная эмуляция RTX 4060**.
- **Отдельный приватный CASE34:** найден в закрытом Google Drive файл `CASE34_source_sha3fb91a7a_private.txt` (`1iVB3TgJhDT-XpNa96ZnLOBykSMtS7sIG`, 13098 байт, `shared=false`). Это метаданные, не подтверждение хеша текста. Ожидаемый SHA оригинала `3fb91a7a0286389073d0da9099d99081b6d49e913b7d34381e359d744d0720cc`. ADC Colab имеет узкий scope для Colab и **не обеспечивает доступ к Drive**.
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
