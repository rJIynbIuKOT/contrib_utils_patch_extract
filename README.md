# contrib_utils_patch_extract

Набор небольших Python-скриптов для подготовки сводных отчётов по составу продукта Tantor: списков contrib-расширений, утилит, внешних программ, патчей и компонентов сборки. Каждый скрипт — самостоятельный, без сторонних зависимостей (только стандартная библиотека Python 3.6+), без сетевых вызовов и работает только с локальными файлами.

Все скрипты следуют общему стилю запуска:

- запускаются из терминала (с аргументом или интерактивно — Enter использует дефолтный путь);
- запускаются двойным кликом из файлового менеджера Ubuntu через `Run in Terminal` (есть shebang, бит исполняемости и LF);
- по завершении ждут нажатия Enter, чтобы можно было прочитать вывод/ошибку;
- сами переключают рабочий каталог на свою папку — выходные файлы создаются рядом со скриптом.

В каждом подкаталоге лежит подробный README с форматом входа/выхода, особенностями обработки и примерами запуска. В корне публикуются только сами скрипты и README — пользовательские входные JSON/SGML и сгенерированные `*.txt`/`*.csv`/`*.sgml` исключены через `.gitignore`.

## Каталоги и скрипты

### `contrib/` — списки contrib-расширений по изданиям

Два независимых скрипта, которые удобно использовать в одном цикле подготовки списков contrib-расширений:

- `contrib.py` — генерирует по изданиям (`be`, `se`, `se-1c`, `certified`, `certified-2`, `free`) текстовые файлы вида `<name> <version> <url>` из `contrib.json`. Версия извлекается из ссылки `current_version` набором регулярных выражений. Дополнительно создаётся сводный `all.txt`. Подробно: [contrib/README.md](contrib/README.md).
- `contrib_from_differences.py` — извлекает плоский список contrib-расширений из раздела `<sect2 id="differences-contrib">` файла `differences.sgml` и пишет имена в `contrib.txt` по одному на строку. Подробно: [contrib/README_contrib_from_differences.md](contrib/README_contrib_from_differences.md).

### `contrib_ext_programs/` — таблица внешних программ

- `ext.py` — генерирует TSV-подобный отчёт `ext.txt` (имя, версия, git-URL, git-тег) из `config.json` по жёстко зашитому в скрипте списку `ENTITIES` (`pipelinedb`, `pg_anon`, `pg_configurator`, `ldap2pg`, `mysql_fdw`, `oracle_fdw`, `pg_timetable`, `pgbouncer`, `tds_fdw`, `wal-g`). Поля читаются из `general.version` и `general.git`. Подробно: [contrib_ext_programs/README.md](contrib_ext_programs/README.md).

### `fstek/` — отчёт для материалов ФСТЭК

- `fstek.py` — формирует `config.txt` со строками `<name> <version> <git_url> <commit_sha>` из `config.json`. В отличие от `contrib_ext_programs/ext.py` обрабатываются **все** ключи верхнего уровня без фильтр-списка; поля берутся из `general.version` и `general.git`. Удобно сохранять результаты как `configC1.txt` / `configC2.txt` для разных уровней. Подробно: [fstek/README.md](fstek/README.md).

### `nexus/` — отчёт по составу сборки (Nexus / артефакты)

- `nexus.py` — формирует `nexus.txt` со строками `<name> <version> <git_url> <commit_sha>` из `nexus.json`. От `fstek/fstek.py` отличается раскладкой JSON: компоненты лежат внутри ключа `components`, и `version`/`git` находятся прямо в компоненте, без вложения в `general`. Подробно: [nexus/README.md](nexus/README.md).

### `patches_gucs_from_confjson/` — pipeline по патчам и GUC

Связанный набор из 5 скриптов (типовой порядок запуска):

1. `patches_for_editions_csv.py` — базовая матрица `patch × edition` из одного `conf.json` (`patches_for_editions.csv`).
2. `patches_and_gucs_csv.py` — по одному репозиторию версии (`tantor-db-*`) строит `patches_and_gucs.csv` с колонками `patch,guc,doc,url`.
3. `patches_and_gucs_csv_all_versions.py` — пакетно запускает предыдущий скрипт для набора версий и сохраняет `patches_and_gucs_<version>.csv`.
4. `summ_patches_and_gucs_csv_all_versions.py` — агрегирует по всем версиям в `summ_patches_and_gucs_all_versions.csv`.
5. `csv_to_conf.py` — конвертирует итоговый CSV в HTML-таблицу для Confluence (`*.confluence.html.txt`).

Практически чаще всего используют цепочку `3 -> 4 -> 5`, а `patches_for_editions_csv.py` запускают отдельно для быстрого среза «патч по изданиям». Подробно: [patches_gucs_from_confjson/README.md](patches_gucs_from_confjson/README.md).

### `patch_to_core_improvements/` — генерация SGML-раздела «Core improvements»

- `generate_core_improvements_sgml.py` — собирает `<sect2 id="differences-core-improvements"> ... </sect2>` для конкретного издания из трёх JSON: `conf.json` (какие патчи входят в издание), `order.json` (порядок и тип элементов — `patch`/`group`), `patch_descriptions.json` (тексты `description_en`, варианты, готовые блоки `sgml_listitem`). На выход — `generated_<edition>.sgml`. Печатает предупреждения о патчах без описаний, пустых описаниях и патчах из `conf.json`, не упомянутых в `order.json`. Подробно: [patch_to_core_improvements/README.md](patch_to_core_improvements/README.md).

### `ppk/` — список компонентов ППК из CycloneDX SBOM

- `ppk.py` — извлекает компоненты из CycloneDX-совместимого SBOM-JSON (например, `ППК_Tantor_16.8.json`) и пишет их в `<stem>.txt` рядом со входным файлом строками `<name> <version> <vcs_url>`. URL берётся из первой записи `externalReferences` с `type == "vcs"`. Подробно: [ppk/README.md](ppk/README.md).

### `utils/` — списки утилит по изданиям + кросс-сверка

- `utils.py` — генерирует **два** файла, которые должны быть идентичны: `utils.txt` (из `utils.json` — деклараций со списком `editions`) и `utils_conf.txt` (из `conf.json` — фактического вхождения утилит в `editions[<ed>].utils`). По завершении явно сообщает, идентичны ли файлы. Поддерживает разные формы аргумента: пустой ввод, путь к директории, путь к `utils.json` или строку-версию (`17_7`, `16_8`) — в этом случае пути собираются по шаблону `VERSION_BASE_TEMPLATE`. Подробно: [utils/README.md](utils/README.md).

## Структура репозитория (кратко)

```
contrib/                       — contrib.py + contrib_from_differences.py
contrib_ext_programs/          — ext.py
fstek/                         — fstek.py
nexus/                         — nexus.py
patches_gucs_from_confjson/    — patches_for_editions_csv.py + patches_and_gucs*.py + csv_to_conf.py
patch_to_core_improvements/    — generate_core_improvements_sgml.py
ppk/                           — ppk.py
utils/                         — utils.py
```

## Требования

- Python 3.6+ (только стандартная библиотека).
- Сеть не нужна ни одному из скриптов.
- Любые входные `*.json`/`*.sgml` — локальные файлы. Если репозиторий-источник приватный, скачайте файл через браузер (`Raw` → «Сохранить как…») и передайте путь скрипту аргументом или интерактивно.
