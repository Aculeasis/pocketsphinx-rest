# docker-starter
Скрипт для управления docker-контейнерами.

## Команды
- `--start` Запустить контейнер. Будет создан, если не существует. Если образ не существует, он будет скачан\собран.
- `--stop` Остановить контейнер.
- `--update` Проверить обновление.
- `--upgrade` Если образа нет, выполнит `--start`. Если образ в хабе изменился, то он будет обновлен а контейнер пересоздан. С ключем `-b` будет всегда пересобирать образ.
- `--remove` Удалить контейнер и образ.
- `--purge` Удалить контейнер, образ и все данные контейнера.
- `--restart` Аналог  `--stop && --start`.
- `--uninstall` Удаляет юниты созданные `--install`. Только для Linux.
## Дополнительные ключи
- `-e KEY=VAL` Задает дополнительные переменные окружения. Аналог `docker -e`
- `-b` Вместо скачивания образа с хаба соберет его локально.
- `-t` Все контейнеры будут обработаны параллельно (Опасно).
- `-f` Позволяет переключать `--upgrade` между локальными сборками и хабом.
- `--install` Создает два юнита systemd - сервис и таймер. Целью будет текущий файл со всеми параметрами (кроме `--install`). Таймер срабатывает каждые 6 часов. Т.е. `./exec.py --install --upgrade -btf` будет запускать `/<path>/exec.py --upgrade -btf`. Имя юнитов по умолчанию `<CONTAINER_NAME>_auto`. Только для Linux.