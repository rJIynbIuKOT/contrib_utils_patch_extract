# generate_core_improvements_sgml.py

Скрипт собирает раздел `<sect2 id="differences-core-improvements"> ... </sect2>` для документации по изданиям `be`, `certified`, `certified_2`, `se`, `se1c`. На вход берёт три JSON-файла (`conf.json`, `order.json`, `patch_descriptions.json`), на выход пишет `generated_<edition>.sgml` для каждого найденного в `conf.json` издания. Издания `free` и `persey` игнорируются.

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

`order.json` и `patch_descriptions.json` по умолчанию всегда берутся **из папки скрипта**, даже если `conf.json` указан из другой директории. Другие пути к ним можно задать флагами `--order` / `--descriptions`.

За один запуск скрипт обрабатывает фиксированный список изданий: `be`, `certified`, `certified_2`, `se`, `se1c`. Если издания нет в `conf.json`, оно пропускается без ошибки. `free` и `persey` не обрабатываются, даже если присутствуют в `conf.json`.

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

Каждый запуск перезаписывает `generated_<edition>.sgml` для всех обработанных изданий.

## Запуск

### Из терминала

Без аргументов — один интерактивный запрос пути к `conf.json` (Enter → дефолтный путь), затем генерация SGML для всех целевых изданий, которые есть в этом файле:

```bash
./generate_core_improvements_sgml.py
# Путь до conf.json (Enter — использовать ./conf.json):
# Источник: локальный файл /.../patch_to_core_improvements/conf.json
# Файл /.../patch_to_core_improvements/generated_be.sgml успешно создан.
# ...
```

Если в запросе ввести путь к `conf.json` из другой папки, `order.json` и `patch_descriptions.json` всё равно берутся из папки скрипта.

Другие пути к JSON-файлам можно задать флагами:

```bash
./generate_core_improvements_sgml.py \
    --conf /path/to/conf.json \
    --order /path/to/order.json \
    --descriptions /path/to/patch_descriptions.json \
    --section-id differences-core-improvements
```

Скрипт сам переключает рабочий каталог на папку, где он лежит, поэтому относительные пути ко всем входам/выходам всегда резолвятся рядом со скриптом — даже если запускать его «из любой точки».

### Через двойной клик в файловом менеджере

Файл уже настроен под запуск из штатного файлового менеджера Ubuntu (есть shebang `#!/usr/bin/env python3`, бит исполняемости установлен, переводы строк LF). Двойной клик → выбрать `Run in Terminal` (или «Запустить в терминале») — откроется окно, скрипт спросит путь до `conf.json`, сгенерирует SGML для всех целевых изданий и после завершения попросит нажать Enter, чтобы окно закрылось.

При запуске без терминала (`Run`) запрос пути к `conf.json` показать негде — будет взят дефолтный `./conf.json`. Для интерактивного выбора пути используйте именно `Run in Terminal`.

## Поведение и ограничения

- Скрипт работает только с локальными файлами и не делает никаких сетевых вызовов.
- При любом исключении (нет файла, битый JSON, отсутствует `editions`/`items_order`, ошибка прав и т.п.) выводится traceback, и скрипт всё равно ждёт нажатия Enter — ошибку успеешь прочитать. Отсутствие конкретного издания из списка `be` / `certified` / `certified_2` / `se` / `se1c` в `conf.json` ошибкой не считается — оно просто пропускается.
- Алиасы патчей не поддерживаются — ключ должен совпадать в `conf.json`, `order.json` и `patch_descriptions.json`. Несовпавшие тихо пропускаются.
- Тексты в `description_en` экранируются автоматически; если в описании уже есть SGML-разметка, она эмитится как есть (эвристика по наличию `<` и `>`).

## Вспомогательный скрипт `contrib_to_sgml.py`

В той же папке лежит маленькая утилита, которая извлекает имена contrib-расширений из `<sect2 id="differences-contrib">` в произвольном `differences.sgml` и пишет их по одному на строку в `contrib.txt`:

```bash
./contrib_to_sgml.py --input differences.sgml --output contrib.txt
```

Сейчас она используется отдельно от `generate_core_improvements_sgml.py` и не приведена к стилю «Run in Terminal + ожидание Enter» — если потребуется, можно адаптировать так же, как остальные скрипты в репозитории.
