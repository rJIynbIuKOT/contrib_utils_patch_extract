# os_from_conf_json.py

Пакетный скрипт: из `conf.json` и `install-binaries*.sgml` нескольких версий Tantor
собирает CSV-матрицы «операционная система × издание».

Для каждого издания рядом стоят две колонки: факт сборки из json и упоминание
в документации. Так видно, где ОС есть в `conf.json`, но нет в sgml, и наоборот.

## Требования

- Python 3.6+ (только стандартная библиотека). Сеть не нужна.
- Локальные checkout-репозитории `tantor-db-*` по путям из `TARGETS`.

## Входные данные

Пути зашиты в `TARGETS` в начале скрипта:

| Версия | Файл |
| ------ | ---- |
| 18 | `/home/kot/repo/tantor-db-18_3/tantor/conf.json` |
| 17 | `/home/kot/repo/tantor-db-17_10/tantor/conf.json` |
| 16 | `/home/kot/repo/tantor-db-16_14/tantor/conf.json` |
| 15 | `/home/kot/repo/tantor-db-15_18/tantor/conf.json` |
| 14 | `/home/kot/repo/tantor-db-14_23/tantor/conf.json` |

Рядом с каждым `conf.json` ожидается каталог `doc/replace_whole_sgml/`.

### `conf.json`

ОС берутся из `run_build_all`: поля `platform` и `edition`.
Если платформа встречается в сборке издания (на любой архитектуре), в json-колонке `y`.

### Документация (sgml)

Список «The list of supported operating systems» из:

| Файл | Колонки |
| ---- | ------- |
| `install-binaries.sgml` | `be_sgml`, `se_sgml`, `se1c_sgml` |
| `install-binaries-certified.sgml` | `certified_sgml` |
| `install-binaries-certified-2.sgml` | `certified_2_sgml` |

У `free` отдельного sgml нет — колонки `free_sgml` нет.
Если sgml-файла нет (например, certified у 14-й версии), соответствующие колонки пустые,
скрипт пишет в терминал `файл не найден` и продолжает работу.

Человекочитаемые имена из sgml (`Ubuntu 22.04`, `ALT 8 SP, Release 10 (c10f2)`)
приводятся к ключам `platform` из json (`ubuntu_22_04`, `altlinux_c10f2`).
Неизвестные формулировки скрипт пытается разобрать эвристикой; если не вышло —
пишет предупреждение и оставляет slug строки как имя ОС.

## Выходные данные

Рядом со скриптом создаются файлы:

- `18.csv`, `17.csv`, `16.csv`, `15.csv`, `14.csv`

Колонки фиксированы для всех версий:

```
os,be,be_sgml,se,se_sgml,se1c,se1c_sgml,certified,certified_sgml,certified_2,certified_2_sgml,free
```

Строки — объединение ОС из json и sgml. `y` — ОС есть в этом источнике.

Пример расхождения: `rosa_12` есть в сборке be/se/se1c, но нет в sgml:

```
rosa_12,y,,y,,y,,,,,,
```

Издание, которого нет в данной версии (например `certified` у 14), даёт пустые колонки.

## Как использовать

Запуск из терминала:

```bash
./os_from_conf_json.py
```

Или через файловый менеджер Ubuntu: «Запустить как приложение» / `Run in Terminal`.

По завершении скрипт ждёт Enter, чтобы можно было прочитать вывод.

При смене веток поправьте пути в `TARGETS`.
