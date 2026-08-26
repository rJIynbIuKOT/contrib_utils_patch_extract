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
  - `doc/src/sgml/config.sgml` — для обратной проверки GUC (без него она станет строже:
    в отчет попадут ванильные параметры PostgreSQL)

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

Скрипт делает проверку в обе стороны:

- прямая — у каждого найденного в коде GUC проверяется наличие описания (колонка `doc`);
- обратная — у каждого описанного GUC проверяется наличие определения в коде.

Результат обратной проверки идет отдельной секцией в конце того же CSV: пустая строка,
строка-заголовок `GUC с описанием, но отсутствующие в коде` в колонке `patch`, дальше сами
GUC в колонке `guc` со своими `doc` и `url`. Заголовок пишется всегда, даже если список пуст.

В колонке `patch` у этих строк — патч, в файлах которого лежит описание (не тот, что
определяет GUC: определения как раз и нет). Патч восстанавливается по месту, где нашелся
`<varname>`:

- для `yes (patch)` — из пути: `tantor/patches/func/large_alloc/0001-….patch` → `func/large_alloc`;
- для `yes (doc)` — из имени файла, где `_` соответствует `/`, а хвост отбрасывается:
  `perf_relocate_sub_plan.sgml` → `perf/relocate_sub_plan`, `func_smgr_create_index.sgml` →
  `func/smgr`, `perf_buf_part1.sgml` → `perf/buf_part`. Кандидаты берутся из `conf.json`
  и из реальных подкаталогов `tantor/patches`, выбирается самое длинное совпадение.

Если описание нашлось в файлах нескольких патчей, они перечисляются через пробел. Если
патч восстановить не удалось, колонка остается пустой.

«Есть в коде» — объединение двух источников:

- `guc.yaml`/`guc_tables.yaml`/`guc_c.yaml` какого-либо патча из `conf.json` (то же
  множество, что попадает в основную таблицу);
- `doc/src/sgml/config.sgml` — ванильная документация PostgreSQL по параметрам ядра.
  Засчитываются только полноценные записи со ссылкой, то есть `<varlistentry id="guc-…">`,
  сразу за которым идет `<term><varname>имя</varname>`. Требование «`<term>` сразу за
  `<varlistentry>`» отсекает вложенные записи с примерами значений (`HIGH`, `+3DES`,
  `!aNULL` у `ssl_ciphers`) — там в `<term>` стоит `<literal>`, а не GUC.

Второй источник нужен, чтобы из отчета ушли ванильные параметры PostgreSQL
(`shared_buffers`, `lock_timeout`, `commit_delay` и т.п.): Tantor их не определяет, но
упоминает в описаниях патчей. Заодно он корректно обрабатывает параметры, уехавшие
в upstream: например, SLRU-буферы были патчем Tantor в 16 и стали GUC ядра в 17.

GUC расширений в `config.sgml` не описаны (у них свои файлы вроде `pgstatstatements.sgml`),
поэтому `pg_stat_statements.*` в секции остаются.

Тег `<varname>` в документации размечает не только GUC — им же оформляют SQL-команды,
значения, типы данных и параметры хранения. Такие имена перечислены в константе
`IGNORED_DOC_VARNAMES` в начале скрипта и в отчет не попадают. Список правится руками
по мере появления новых ложных срабатываний.

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
- `doc` содержит версии, где найден `<varname>…</varname>`, и статус (`18 17 yes (doc)`, `18 yes (patch); 17 yes (doc, patch)` и т.п.; `no` — нигде). Если набор версий в `version` не совпадает с набором версий в `doc` (в любую сторону), в начало `doc` ставится `!`.
- `url` берется первый непустой (в порядке от новых к старым).

После основной таблицы тем же способом (пустая строка + строка-заголовок
`GUC с описанием, но отсутствующие в коде`) идет вторая таблица — сводка секций из файлов
отдельных версий. Колонки те же: патчи с лишним описанием — в `patch`, имя в `guc`, версии,
где GUC описан и при этом отсутствует в коде, — в `version`, статус документации — в `doc`.
Строка здесь одна на GUC, поэтому патчи из разных версий объединяются в одну ячейку.

Скрипт печатает эту сводку и в терминал, чтобы не открывать CSV ради пары строк.

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

Если во входном CSV есть секция `GUC с описанием, но отсутствующие в коде`, она выводится
второй HTML-таблицей под своим заголовком.

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
