pocketsphinx-rest
============
Простой веб-сервис распознавания речи с помощью [PocketSphinx](https://github.com/cmusphinx/pocketsphinx)

## Установка

### Готовый докер
На aarch64 (Например Orange Pi Prime и прочие H5):

`docker run -d -p 8085:8085 aculeasis/pocketsphinx-rest:arm64v8`

На обычной x86_64:

`docker run -d -p 8085:8085 aculeasis/pocketsphinx-rest:amd64`

## API
Просто отправить файл через POST

    POST /stt
    Host: SERVER
    Content-Type: audio/x-wav 
    (wav file)

Требования к файлу:
- Формат - wav
- Число каналов  - 1 (моно)
- Частота дискретизации  - 16 000 Гц
- Квантование - 16 бит.

Если нужно, перекодируйте файл перед отправкой.

Сервер пришлет ответ в json, где:
- `code` - код ошибки или 0
- `text` - распознанный текст если code равен 0 иначе сообщение об ошибке

## Работа с API
[examples](https://github.com/Aculeasis/pocketsphinx-rest/tree/master/example)

Для проверки сервера можно использовать `pocketsphinx_rest_file.py FILE [URL]`

## Примечания
- Из-за большого словаря для запуска нужно минимум 1 GB RAM.
- Распознование происходит в однопоточном режиме, что накладывает высокие требования на производительность CPU core. На OPI Prime распознование фраз занимает от 10 до 40 секунд.
- Веб-сервер также запущен в однопоточном режиме.
- Качество распознования ~~оставляет желать лучшего~~ ужасно.
- Поддерживается только русский язык.

## Ссылки
- PocketSphinx https://github.com/cmusphinx/pocketsphinx
- Pocketsphinx Python https://github.com/bambocher/pocketsphinx-python
