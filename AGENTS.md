# AVRORA / PsyAI Colab launcher — постоянные инструкции для агентов

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
