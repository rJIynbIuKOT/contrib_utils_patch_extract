# patches_gucs_from_confjson

Каталог содержит **связанный pipeline из 5 скриптов** для подготовки отчета по патчам и GUC:

1. `patches_for_editions_csv.py`
2. `patches_and_gucs_csv.py`
3. `patches_and_gucs_csv_all_versions.py`
4. `summ_patches_and_gucs_csv_all_versions.py`
5. `csv_to_conf.py`

Для сбора и проверки всех гуков нужно использовать следующий порядок действий:

1. Проверить пути ко всем веткам tantor-db в `patches_and_gucs_csv_all_versions.py` и запустить его. Получим набор `patches_and_gucs_14.csv`, `patches_and_gucs_15.csv` и так далее.
2. Запустить `summ_patches_and_gucs_csv_all_versions.py` для объединения `patches_and_gucs_14.csv`, `patches_and_gucs_15.csv` и так далее в `summ_patches_and_gucs_all_versions.csv`.
3. Запустить `csv_to_conf.py` для получения из `summ_patches_and_gucs_all_versions.csv` HTML-таблицы в файле `summ_patches_and_gucs_all_versions.csv.confluence.html.txt`. HTML-таблицу из этого файла можно вставлять в confluence и сравнивать с предыдущей.

Ниже описание в рабочем порядке: что делает каждый шаг и как его запускать.

## Что нужно заранее

- Python 3.6+ (только стандартная библиотека).
- Локальные checkout-репозитории `tantor-db-*` для нужных версий.
- Для шага с ссылками на документацию в репозитории должны быть:
  - `tantor/conf.json`
  - `tantor/patches/...`
  - `tantor/doc/insert_part_sgml/...`
  - `tantor/doc/output/sphinx_html/ru/<version>/<edition>/*.html`

## 1) `patches_for_editions_csv.py`

### Назначение

Базовая матрица `patch × edition` из одного `conf.json`.

Выход: `patches_for_editions.csv` с колонками:
`patch,be,se,se1c,certified,certified_2,free`.

### Как использовать

Запуск с интерактивным вводом:

```bash
./patches_for_editions_csv.py
```

Запуск с путем к `conf.json`:

```bash
./patches_for_editions_csv.py ~/repo/tantor-db-18_1/tantor/conf.json
```

Когда применять: если нужно быстро увидеть, в какие издания попадает каждый патч, без анализа GUC.

## 2) `patches_and_gucs_csv.py`

### Назначение

Для одного репозитория версии (`tantor-db-18_1`, `tantor-db-17_9` и т.д.) строит файл:

- `patches_and_gucs.csv`

Формат:

- `patch` — патч;
- `guc` — найденный GUC из `guc.yaml`/`guc_tables.yaml`/`guc_c.yaml`;
- `doc` — признак документации (`no` / `yes (...)`);
- `url` — ссылка на HTML-документацию (если найден якорь GUC).

### Как использовать

Рекомендуемый запуск (патчи без GUC не включать):

```bash
./patches_and_gucs_csv.py ~/repo/tantor-db-18_1 --exclude-empty
```

Если нужно оставить патчи без GUC:

```bash
./patches_and_gucs_csv.py ~/repo/tantor-db-18_1 --include-empty
```

Это ключевой шаг пайплайна: именно он собирает данные по GUC и документации.

## 3) `patches_and_gucs_csv_all_versions.py`

### Назначение

Пакетный запуск шага 2 для всех версий из `TARGETS` и сохранение отдельных файлов:

- `patches_and_gucs_18.csv`
- `patches_and_gucs_17.csv`
- `patches_and_gucs_16.csv`
- `patches_and_gucs_15.csv`
- `patches_and_gucs_14.csv`

### Как использовать

1. Открой `patches_and_gucs_csv_all_versions.py`.
2. Проверь/обнови пути в `TARGETS` под свои локальные репозитории.
3. Запусти:

```bash
./patches_and_gucs_csv_all_versions.py
```

Использовать, когда нужен одинаковый отчет сразу по нескольким мажорным версиям.

## 4) `summ_patches_and_gucs_csv_all_versions.py`

### Назначение

Агрегирует версии в единый файл:

- `summ_patches_and_gucs_all_versions.csv`

Итоговая строка — уникальная пара `patch + guc`, где:

- `version` содержит список версий, где пара встречалась;
- `doc` берется из самой новой версии;
- `url` берется первый непустой (в порядке от новых к старым).

### Как использовать

После генерации файлов `patches_and_gucs_<version>.csv` запусти:

```bash
./summ_patches_and_gucs_csv_all_versions.py
```

Если есть расхождения `doc` между версиями, скрипт печатает предупреждение в терминал.

## 5) `csv_to_conf.py`

### Назначение

Конвертирует CSV-сводку в HTML-таблицу для Confluence.

По умолчанию (без аргументов) берет входной файл `summ_patches_and_gucs_all_versions.csv`
рядом со скриптом и создает:

- `<input_csv>.confluence.html.txt`

Колонка `guc` становится HTML-ссылкой, если в CSV есть `url`.

Скрипт можно запускать прямо из контекстного меню Ubuntu через пункт
«Запустить как приложение»: входной файл по умолчанию берется относительно самого
скрипта, а после завершения работы окно ждет нажатия Enter.

### Как использовать

Запуск с файлом по умолчанию:

```bash
./csv_to_conf.py
```

С явным входным файлом:

```bash
./csv_to_conf.py ./summ_patches_and_gucs_all_versions.csv
```

С явным выходным именем:

```bash
./csv_to_conf.py ./summ_patches_and_gucs_all_versions.csv -o ./confluence_table.html.txt
```

## Быстрый рабочий сценарий

Обычно используют так:

1. Проверяют пути в `patches_and_gucs_csv_all_versions.py` (`TARGETS`).
2. Запускают `patches_and_gucs_csv_all_versions.py`.
3. Запускают `summ_patches_and_gucs_csv_all_versions.py`.
4. Запускают `csv_to_conf.py` для подготовки таблицы в Confluence.

`patches_for_editions_csv.py` запускают отдельно как дополнительный срез `patch × edition` по одному `conf.json`.
