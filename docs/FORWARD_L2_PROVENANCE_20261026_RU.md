# AVRORA — доказательная запись Bybit L50 + publicTrade (2026-10-26)

## Назначение

Задача — получить **новые** рыночные свидетельства из публичного WebSocket Bybit для шести инструментов BTC, ETH, SOL, NEAR, LINK, XRP, не выдавая ретроспективные ZIP за доступные в прошлом данные. Этот пакет **не размещает ордера**, не вызывает приватное API, не использует API-ключи, не запускает таймер и не меняет REAL=OFF / HOLDOUT=SEALED.

Официальный источник: `wss://stream.bybit.com/v5/public/linear`, каналы `orderbook.50.SYMBOL` и `publicTrade.SYMBOL`. Официальные спецификации: <https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook> и <https://bybit-exchange.github.io/docs/v5/websocket/public/trade>.

## Прямой результат 26 октября

- 13 офлайн unit-тестов: PASS.
- Проверены непрерывная SHA256-цепочка, сохранённые timestamps, snapshot → delta, monotonic `seq` / `u`, шестёрка инструментов, знаки встречных сделок, цена / размер, нарушения в источнике и контроль отсутствующих каналов.
- Пробный 2-секундный запуск от текущей среды: **BLOCKED_CAPTURE, DNS**, 0 записанных событий. Сохранён `probe/manifest.json`. Прямой read-only Bybit REST из доступного web-окружения: HTTP 403. Поэтому **нет доказанного успешного сетевого live-запуска**.
- Исторический набор за 23–25 октября и независимый price-path моделируемый результат для 192 кандидатов не считаются prospective OOS или proof maker fill.
- Проверен каталог проекта в Google Drive: `/AVRORA_DATA/P900_FULL_BYBIT/raw/trades` и нормализованные `mark_15m`, `funding` пока пустые в доступном представлении; в `/AVRORA_DATA/P900_HF_BYBIT/futures/15m` есть 21 Parquet, в том числе шесть нужных символов, но это другой 15-минутный исторический источник, **не L2/queue**.

## Использование только на машине с разрешённым доступом к публичному Bybit WebSocket

Установить пакет `websockets` в используемую среду Python (в текущей тестовой среде проверено с 16.0). Один безопасный сеанс для 6 символов:

```powershell
python -m pip install "websockets==16.0"
python -m tools.forward_l2_provenance capture --output "E:\AVRORA_L2_EVIDENCE\run_001" --seconds 60
python -m tools.forward_l2_provenance verify --events "E:\AVRORA_L2_EVIDENCE\run_001\events.jsonl" --output "E:\AVRORA_L2_EVIDENCE\run_001\independent_qc.json"
python -m unittest discover -s tests -p test_forward_l2_provenance.py -v
```

Код не использует прокси и не меняет страну подключения. Если у провайдера ограничение IP/юрисдикции, нужно **допустимое подключение**, а не обход ограничения. Этот 60-секундный сеанс — краткая проверка канала, **не полноценная 15-минутная история и не исполнение ордера**. Скрипт ограничен максимум 300 секундами и 80 МБ данных на сеанс, обрывает невалидные данные.

## Верификация и что нельзя утверждать

`events.jsonl` сохраняет кадры по порядку, локальное UNIX/monotonic время при получении, исходные сообщения, `seq`, `u`, `cts`, `T`, `S`, цену и объём сделки. Цепочка SHA256 позволяет выявлять последующее повреждение файла, но **не является криптографическим доказательством истинности часов, независимости источника или невозможности подмены файла вместе с манифестом**.

`manifest.json` содержит статус `PASS_RECORDED_PUBLIC_FEED_COVERAGE_ONLY` только если действительно наблюдались снимок и дельта L50 и хотя бы одна сделка каждого из шести инструментов. При сбое сети — `BLOCKED_CAPTURE` или `BLOCKED_VERIFY`. Если каналы неполные — `BLOCKED_INCOMPLETE_L2_AND_TRADES`. Ни один статус не должен повышать `maker_fill_verified`, `actual_order_receipts_verified`, `queue_position_verified`, `oos_verified` или `independent_economic_check2` в `true`.

**Ключевое ограничение:** сообщения L50 показывают агрегированные уровни, не позицию нашей заявки в очереди. Bybit также указывает, что RPI-ордера не попадают в публичный стакан. Для реального maker fill необходимы приватные квитанции `order/execution` или эксперимент с подлинной заявкой, который здесь **не выполняется**. В дальнейшем для исследования заполнения допустимы консервативные сценарии с явными допущениями, но не отождествление trade-through с фактическим исполнением.

## Дальнейшая безопасная интеграция

Встраивать только в существующий **публичный** workflow `vicrex/avrora-colab-launcher`, без нового cron и без private Actions, с явным gate `AVRORA_FORWARD_CAPTURE_ENABLED`. Текущий GitHub US runner блокируется Bybit HTTP 403, поэтому запуск на нём заранее считать WAIT/BLOCKED, а не успешным. Доставка в закрытый Google Drive только после источника + SHA256/readback, без секретов на публичном репозитории. Для экономического CHECK2 отдельно нужны MarkPrice, funding, причинность по времени и настоящие подтверждения ордеров.
