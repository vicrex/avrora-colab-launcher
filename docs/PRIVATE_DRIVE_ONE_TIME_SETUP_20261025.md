# AVRORA — одноразовая безопасная настройка записи полного отчёта в Drive
Дата: 25 октября 2026. **Это руководство для владельца**, не объявление об успешном получении OAuth.

## Уже исправлено в GitHub

- PR #61 добавил обязательную запись полного приватного отчёта из 64 кандидатов в Drive, побайтовое чтение обратно и SHA-256 ACK. Отказ записи = FAILED, а не ложный SUCCESS.
- PR #62 исправил отсутствие checkout публичных скриптов и отделил Drive-secret `AVRORA_PRIVATE_DRIVE_ADC_JSON_B64` от Colab-only `AVRORA_COLAB_ADC_JSON_B64`.
- Запуск [40181486935](https://github.com/vicrex/avrora-colab-launcher/actions/runs/40181486935) уже вычислил 64 модели, но честно завершился `BLOCKED_PRIVATE_DRIVE_ADC_MISSING`. Он **не** сохранил полный JSON.
- Новых почасовых таймеров и Cloud Browser/Work нет. REAL OFF; HOLDOUT SEALED.

## Почему требуется личная авторизация

GitHub secret отсутствует. Мы **не можем** получить из ChatGPT Google Drive-коннектора OAuth refresh-token для автономного GitHub runner и не должны копировать секреты через публичные ссылки, чат или issues. Исходный Colab-токен имеет только Colab/email scopes; Google Drive выдавал 403.

**Важное предупреждение:** Для записи в существующую закрытую папку через текущий REST-код используется `https://www.googleapis.com/auth/drive`. Этот restricted scope потенциально даёт программе доступ ко **всему Drive соответствующего Google-аккаунта**. Сам код обращается только к папке AVRORA, но OAuth разрешение технически шире. Безопаснее использовать отдельный Google-аккаунт, которому владелец предоставил Writer только на папку AVRORA. Не используйте `drive.file` вслепую: он не гарантирует доступ к уже существующей папке.

## Один раз в Google Cloud Console

1. Выберите Google-аккаунт, который будет выполнять архивирование. Если это отдельная учётная запись, владелец Drive должен поделиться папкой `AVRORA_WAVE5_RESEARCH_20261020` с ней как **Редактором**.
2. В Google Cloud Console в своём проекте включите **Google Drive API** и в **Google Auth Platform** настройте OAuth consent. При режиме Testing добавьте выбранный Google-аккаунт как test user.
3. В **Clients / OAuth client IDs** создайте OAuth client типа **Desktop app** и скачайте JSON в свой Google Cloud Shell. Не публикуйте его в GitHub и не присылайте в чат.
4. Для долгого автономного режима учитывайте: **External + Testing** обычно выдаёт refresh-token, истекающий через **7 дней** для Drive scope; до эксплуатационного режима потребуется изменить publishing status на **In production**, если Google разрешит, с учётом правил проверки restricted scope. Один успешный час не доказывает многомесячный доступ.

## Запуск существующим Cloud Shell

В своём Google Cloud Shell, авторизованном GitHub-аккаунтом `vicrex`:

```bash
cd ~/avrora-colab-launcher
git pull --ff-only
bash tools/connect_private_drive_cloud_shell.sh "$HOME/client_secret.json"
```

Замените путь на **точный путь к скачанному Desktop OAuth client JSON**, если он называется иначе.

Скрипт открывает отдельное согласие только на Drive, используя ваш OAuth client через `gcloud auth application-default login --client-id-file=... --scopes=... --no-launch-browser`. Код подтверждения вводите только в Cloud Shell, **никогда в ChatGPT**. Cloud SDK ADC помещён во временную директорию, не затирает системные учётные данные Cloud Shell.

После авторизации скрипт **до установки секрета**:
- проверяет фактически выданные Drive scopes, отклоняя лишние `cloud-platform` и Colab;
- проверяет доступ к конкретной приватной папке;
- создаёт небольшой безобидный тестовый файл внутри папки, считывает его обратно и проверяет SHA;
- удаляет тестовый файл;
- только после этого шифрует и сохраняет новый GitHub Actions secret `AVRORA_PRIVATE_DRIVE_ADC_JSON_B64`, проверяя наличие имени в GH;
- удаляет временные файлы учётных данных.

Ожидаемый маркер: `PASS_PRIVATE_DRIVE_SECRET_INSTALLED_AND_VERIFIED_BY_NAME`.
На отказе любой проверки токен в GitHub не устанавливается.

## Что проверять после

Откройте существующий [публичный GitHub Actions multifamily workflow](https://github.com/vicrex/avrora-colab-launcher/actions/workflows/multifamily-sweep-smoke.yml) после **следующего уже предусмотренного запуска**. Шаг `Upload full private 64-candidate ledger...` обязан выдать `PASS_PRIVATE_MULTIFAMILY_DRIVE_READBACK_SHA` и JSON ACK artifact. Затем нужна внешняя проверка **полного** сохранённого JSON по SHA, append-only запись в private graph, независимый CHECK2 и два отдельных автоматических полных цикла; без этого статус неполный. GitHub job зелёного цвета **недостаточно**.

Не запускать REAL, не открывать holdout, не менять расписание, не переносить private стратегии/свечи в публичные GitHub artifacts.

## Источники

Google Cloud ADC: https://docs.cloud.google.com/sdk/gcloud/reference/auth/application-default/login
Google Drive scopes: https://developers.google.com/workspace/drive/api/guides/api-specific-auth
Google OAuth refresh token limits: https://developers.google.com/identity/protocols/oauth2
