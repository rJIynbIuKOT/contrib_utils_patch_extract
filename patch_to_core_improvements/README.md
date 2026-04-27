# generate_core_improvements_sgml.py

Скрипт собирает раздел `<sect2 id="differences-core-improvements"> ... </sect2>` для документации по конкретному изданию (`be`, `se`, `se1c`, `certified`, `certified_2`, `free` и т.п.). На вход берёт три JSON-файла рядом со скриптом (`conf.json`, `order.json`, `patch_descriptions.json`), на выход пишет `generated_<edition>.sgml`.

В этой же папке лежит вспомогательный скрипт `contrib_to_sgml.py` — он извлекает плоский список contrib-расширений из `differences.sgml` и используется отдельно (его README не выкладывается отдельно, см. конец этого документа).

## Требования

- Python 3.6+ (используется только стандартная библиотека). Сеть не нужна.

## Входные данные

Скрипту нужны три JSON-файла:

| Файл                       | Что внутри                                                                                          |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| `conf.json`                | Корневой объект с ключом `editions`. У каждого издания (`editions["se"]["patches"]` и т.п.) — список патчей, попадающих в это издание. |
| `order.json`               | Корневой объект с `items_order` — список элементов в порядке появления в SGML (`type` = `"patch"` либо `"group"`, поле `key`, опционально `variant`). Опциональный `section_id`. |
| `patch_descriptions.json`  | Словарь `patches` (по ключу патча → описание/варианты) и `groups` (для составных листайтемов). |

Дефолтное расположение всех трёх — рядом со скриптом. Конкретный путь к `conf.json` можно указать тремя способами:

1. Запустить без аргументов — скрипт интерактивно спросит «Путь до conf.json (Enter — использовать ./conf.json)».
2. Передать через флаг `--conf /path/to/conf.json`.
3. Положить файл рядом со скриптом и запустить без флагов / без интерактива.

Если `conf.json` указан **не** в папке скрипта, `order.json` и `patch_descriptions.json` по умолчанию ищутся **в той же папке, что и `conf.json`** — отдельно их пути спрашиваются только в крайнем случае (через флаги `--order` / `--descriptions`).

«Главным параметром» от запуска к запуску является **edition** — короткое имя издания. Скрипт принимает его первым позиционным аргументом командной строки или, при отсутствии, спрашивает интерактивно, показывая список доступных изданий из `conf.json`.

## Логика и обработка

- Из `conf.json` берётся набор патчей конкретного издания (`edition_patches`).
- По `items_order` из `order.json` строится итоговый SGML: сохраняется порядок и типы (`patch`, `group`).
- Тексты берутся из `patch_descriptions.json`:
  - для патча — `description_en` (или `variants[<variant>]`, если в `order.json` указан вариант);
  - для группы — либо готовый блок `sgml_listitem` (если задан), либо `description_en` группы; при необходимости текст экранируется (`xml.sax.saxutils.escape`), но если текст уже похож на SGML (содержит `<...>`), он эмитится как есть.
- Группа `func/query_masking perf/pgss_sampling` обрабатывается отдельно: если в издании присутствуют оба патча — печатается `sgml_listitem` группы; если только один — печатается отдельный `<listitem>` для этого патча.
- Группа `func/backtrace func/log_version func/controlfile` имеет приоритет: если в `order.json` есть группа и все три патча присутствуют в издании, индивидуальные `<listitem>` для этих трёх патчей не эмитятся.
- Алиасов нет: ключ из `order.json` должен **точно** совпадать с ключом из `conf.json`/`patch_descriptions.json`. Несовпавшие тихо пропускаются.

Дополнительно скрипт печатает три типа предупреждений (не падая на них):

- `[WARN] Missing patch descriptions ...` — патч есть в `conf.json`, но описание отсутствует и не покрыто группой.
- `[WARN] Empty descriptions ...` — описание есть в `patch_descriptions.json`, но пустое (и нет ни одного непустого варианта).
- `[WARN] Patches from conf not mentioned in order.json ...` — патч есть в `conf.json`, но не упомянут в `order.json`, поэтому в SGML не попадёт.

## Выходные данные

Файл `generated_<edition>.sgml` рядом со скриптом — единый блок вида:

```sgml
  <sect2 id="differences-core-improvements">
    <title>Core improvements</title>
      <itemizedlist spacing="compact">
        <listitem>
          <para>
            <!-- perf/pglz -->
            Optimized <literal>pglz</literal> data compression algorithm (~1.4 times).
          </para>
        </listitem>
        ...
      </itemizedlist>
  </sect2>
```

Имя выходного файла можно переопределить через `-o` / `--output`. По умолчанию каждый запуск перезаписывает свой `generated_<edition>.sgml`.

## Запуск

### Из терминала

С явным аргументом — самое короткое:

```bash
./generate_core_improvements_sgml.py se
./generate_core_improvements_sgml.py certified
./generate_core_improvements_sgml.py se1c -o se1c.sgml
```

Без аргумента — два интерактивных запроса (Enter в первом → дефолтный путь, во втором без ввода → понятная ошибка):

```bash
./generate_core_improvements_sgml.py
# Путь до conf.json (Enter — использовать ./conf.json):
# Источник: локальный файл /.../patch_to_core_improvements/conf.json
# Доступные издания: be, certified, certified_2, free, se, se1c
# Введите edition (например, se):
```

Если в первом запросе ввести путь к `conf.json` из другой папки, `order.json` и `patch_descriptions.json` будут автоматически взяты из той же папки.

Если хочется указать другие пути к JSON-файлам — флаги `--conf`, `--order`, `--descriptions` остаются как в исходной версии:

```bash
./generate_core_improvements_sgml.py se \
    --conf /path/to/conf.json \
    --order /path/to/order.json \
    --descriptions /path/to/patch_descriptions.json \
    --section-id differences-core-improvements
```

Скрипт сам переключает рабочий каталог на папку, где он лежит, поэтому относительные пути ко всем входам/выходам всегда резолвятся рядом со скриптом — даже если запускать его «из любой точки».

### Через двойной клик в файловом менеджере

Файл уже настроен под запуск из штатного файлового менеджера Ubuntu (есть shebang `#!/usr/bin/env python3`, бит исполняемости установлен, переводы строк LF). Двойной клик → выбрать `Run in Terminal` (или «Запустить в терминале») — откроется окно, скрипт спросит edition (со списком известных), и после завершения попросит нажать Enter, чтобы окно закрылось.

При запуске без терминала (`Run`) интерактивный запрос показать негде, а edition без аргумента не определён — будет понятная ошибка в выводе. Поэтому при двойном клике используйте именно `Run in Terminal`.

## Поведение и ограничения

- Скрипт работает только с локальными файлами и не делает никаких сетевых вызовов.
- При любом исключении (нет файла, битый JSON, неизвестное издание, отсутствует `editions`/`items_order`, ошибка прав и т.п.) выводится traceback, и скрипт всё равно ждёт нажатия Enter — ошибку успеешь прочитать.
- Алиасы патчей не поддерживаются — ключ должен совпадать в `conf.json`, `order.json` и `patch_descriptions.json`. Несовпавшие тихо пропускаются.
- Тексты в `description_en` экранируются автоматически; если в описании уже есть SGML-разметка, она эмитится как есть (эвристика по наличию `<` и `>`).

## Вспомогательный скрипт `contrib_to_sgml.py`

В той же папке лежит маленькая утилита, которая извлекает имена contrib-расширений из `<sect2 id="differences-contrib">` в произвольном `differences.sgml` и пишет их по одному на строку в `contrib.txt`:

```bash
./contrib_to_sgml.py --input differences.sgml --output contrib.txt
```

Сейчас она используется отдельно от `generate_core_improvements_sgml.py` и не приведена к стилю «Run in Terminal + ожидание Enter» — если потребуется, можно адаптировать так же, как остальные скрипты в репозитории.
