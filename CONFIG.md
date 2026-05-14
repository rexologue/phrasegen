# CONFIG.md

Этот файл — полный справочник по конфигу генератора.
Если поле поддерживается кодом, оно описано здесь.

## Top-Level Schema

```yaml
run: {}
api: {}
sampling: {}
output: {}
parser: {}
prompts: {}
diversity_profiles: {}
dedup_profiles: {}
callbacks: {}
rules: []
```

Обязательные top-level блоки:

- `run`
- `api`
- `output`
- `rules`

Остальные имеют дефолты.

Все YAML-файлы читаются как UTF-8. Относительные пути считаются от папки
конфига, а не от текущей рабочей директории.

## run

```yaml
run:
  name: "demo"
  random_seed: 42
  resume: true
  prompts_per_cycle: 4
  max_requests_per_rule: 10000
  max_consecutive_empty_cycles: 50
```

Поля:

- `name`  
  Обязательное имя запуска. Попадает в `report.json` и `meta.run_name`.

- `random_seed`  
  Seed для sampling-а diversity. Не управляет случайностью внешней модели.

- `resume`  
  `true`: читать существующие `per_rule/*.jsonl` и восстановить dedup-state.  
  `false`: очистить `dataset.jsonl` и `per_rule/*.jsonl` перед запуском.

- `prompts_per_cycle`  
  Сколько prompt-запросов строить за один цикл rule.
  Фактический параллелизм также ограничен `api.concurrency`.

- `max_requests_per_rule`  
  Максимум API-запросов на один rule. Это защита от бесконечного цикла.

- `max_consecutive_empty_cycles`  
  Сколько циклов подряд можно не принять ни одного кандидата.
  Если лимит достигнут, rule получает статус `empty_cycle_limit_reached`.

## api

```yaml
api:
  base_url: "https://api.example.com/v1"
  endpoint: "/chat/completions"
  model: "example-model"
  api_key_env: "OPENAI_API_KEY"
  api_key: null
  timeout_sec: 120
  max_retries: 3
  retry_sleep_sec: 2
  concurrency: 4
  headers: {}
```

Поля:

- `base_url`  
  Обязательный base URL OpenAI-compatible API.

- `endpoint`  
  Путь chat completions endpoint. Дефолт: `/chat/completions`.

- `model`  
  Обязательное имя модели для тела запроса.

- `api_key_env`  
  Имя переменной окружения с API key. Если ключ не нужен, используй `null`.

- `api_key`  
  Inline API key. Работает, но обычно лучше использовать `api_key_env`.

- `timeout_sec`  
  HTTP timeout одного запроса.

- `max_retries`  
  Количество повторов после ошибки.

- `retry_sleep_sec`  
  Базовая задержка между повторами. Реальная задержка умножается на номер попытки.

- `concurrency`  
  Максимум одновременных HTTP-запросов.

- `headers`  
  Дополнительные HTTP headers.

Тело запроса всегда содержит:

```json
{
  "model": "...",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ]
}
```

## sampling

```yaml
sampling:
  temperature: 0.9
  top_p: 0.9
  max_tokens: 512
  presence_penalty: null
  frequency_penalty: null
  stop: []
  extra_body: {}
```

Поля:

- `temperature`  
  Передается в API request body.

- `top_p`  
  Передается в API request body.

- `max_tokens`  
  Максимум выходных токенов.

- `presence_penalty`  
  Если не `null`, передается в API.

- `frequency_penalty`  
  Если не `null`, передается в API.

- `stop`  
  Список stop strings.

- `extra_body`  
  Любые дополнительные поля тела запроса. Например:

```yaml
extra_body:
  seed: 42
  top_k: 40
```

Engine не интерпретирует `extra_body`, а просто добавляет его в JSON body.

## output

```yaml
output:
  base_dir: "./out/demo"
  flush_every: 100
  report_filename: "report.json"
  dataset_filename: "dataset.jsonl"
  per_rule_dir: "per_rule"
  rejection_sample_limit_per_rule: 100
```

Поля:

- `base_dir`  
  Папка output-артефактов.

- `flush_every`  
  Размер буфера JSONL-записи.

- `report_filename`  
  Имя единственного mutable JSON-report.

- `dataset_filename`  
  Имя общего JSONL-датасета.

- `per_rule_dir`  
  Папка отдельных JSONL-файлов по rules.

- `rejection_sample_limit_per_rule`  
  Максимум rejection samples в `report.json` для каждой rule.

Output structure:

```text
base_dir/
  report.json
  dataset.jsonl
  per_rule/
    crm_mentions.jsonl
    numeric_phrases.jsonl
```

## parser

```yaml
parser:
  type: "json_array"
```

Допустимые значения `type`:

- `json_array`  
  Ответ модели должен быть JSON-массивом строк:

```json
["text one", "text two"]
```

- `answer_tags`  
  Engine извлекает текст из тегов:

```text
<answer>text one</answer>
<answer>text two</answer>
```

- `lines`  
  Каждая непустая строка считается кандидатом.
  Этот parser самый терпимый, но менее надежный.

## prompts

```yaml
prompts:
  system_template: "..."
  system_template_path: null
  user_template: "..."
  user_template_path: null
  output_contract_template: "..."
  output_contract_template_path: null
```

Каждый template можно задать inline или через файл:

- `system_template` или `system_template_path`
- `user_template` или `user_template_path`
- `output_contract_template` или `output_contract_template_path`

Если задан `*_path`, он имеет приоритет над inline-значением.

### user_template

`user_template` — основной шаблон пользовательского сообщения, которое уйдет
в модель как message с ролью `user`.

Шаблон рендерится ядром через Python `str.format(...)`. Это значит:

- все placeholders пишутся в фигурных скобках: `{goal}`;
- неизвестный placeholder вызовет ошибку запуска;
- если в prompt нужен буквальный символ `{` или `}`, его надо экранировать:
  `{{` и `}}`;
- phone-specific, domain-specific и runtime payload не должны попадать сюда
  напрямую, если ядро о них не знает. Для этого используется `pre_extension`
  callback.

Доступные placeholders:

- `{rule_id}` — `rule.id`
- `{batch_size}` — `rule.batch_size`
- `{goal}` — `rule.goal`
- `{positive_examples}` — bullet list из `examples.positive`
- `{negative_examples}` — bullet list из `examples.negative`
- `{checks}` — bullet list описаний built-in checks
- `{diversity}` — bullet list sampled diversity context
- `{output_contract}` — rendered `output_contract_template`

Порядок сборки prompt-а:

```text
system_template
user_template
  -> ядро подставляет placeholders
  -> ядро добавляет rendered output_contract через {output_contract}
  -> pre_extension callbacks могут изменить готовый user prompt
  -> system + user отправляются в API
```

Разделение ответственности:

- `user_template` отвечает за общий способ постановки задачи модели;
- `rule.goal` отвечает за смысл конкретной категории;
- `rule.examples` показывают хорошие и плохие результаты;
- `rule.checks` превращаются в текстовое описание жестких проверок;
- `diversity` добавляет случайный контекст, но не валидирует результат;
- `output_contract_template` описывает формат ответа модели;
- `pre_extension` добавляет runtime payload: конкретный номер, case, fragment,
  внешний контекст из файла и т.п.

Минимальный пример:

```text
Сгенерируй {batch_size} текстов для rule "{rule_id}".

Цель:
{goal}

Хорошие примеры:
{positive_examples}

Проверки:
{checks}

{output_contract}
```

Для `phone_extraction` конкретный номер не находится в `user_template`.
Сначала ядро заполняет общий шаблон, а затем callback `inject_phone_case`
добавляет блок вида:

```text
PHONE_EXTRACTION_CASE
case_id: ...
expected_extraction_result: ...
Source dictation to preserve exactly:
<<<...>>>
```

Это сделано специально: один и тот же шаблон можно переиспользовать, а
конкретные варианты брать из внешнего `cases.jsonl` во время генерации.

Дефолтный output contract просит JSON array of strings.
Это можно override-нуть, но parser должен соответствовать contract-у.

## diversity_profiles

```yaml
diversity_profiles:
  business_ru:
    dimensions:
      scenario:
        - "сообщение в рабочем чате"
        - "короткий звонок клиенту"
      style:
        - "деловой"
        - "разговорный"
    sample:
      scenario: 1
      style: 1
```

`diversity_profiles` — именованный набор prompt-контекстов.

Поля profile:

- `dimensions`  
  Mapping `dimension_name -> list[str]`.
  Названия dimensions произвольные: `scenario`, `intent`, `style`, `domain`,
  `tone`, `format`, `audience` и т.п.

- `sample`  
  Mapping `dimension_name -> int`.
  Показывает, сколько элементов случайно взять из каждой dimension на один prompt.

Diversity не является проверкой. Он только помогает prompt-у не повторяться.
Если нужно жестко требовать свойство текста, используй `checks`.

Rule подключает profile так:

```yaml
rules:
  - id: "crm"
    diversity_profile: "business_ru"
```

Если `diversity_profile` не задан, prompt получает пустой diversity context.

## dedup_profiles

```yaml
dedup_profiles:
  smart_text:
    scope: "rule"
    exact: true
    normalization:
      lowercase: true
      collapse_spaces: true
      trim_punctuation: true
      replace_yo: true
    prefix_limit:
      enabled: true
      words: 4
      max_count: 8
    ngram_similarity:
      enabled: true
      ngram: 3
      threshold: 0.88
      max_compare: 1000
```

Поля:

- `scope`  
  `rule`: dedup внутри каждого rule отдельно.  
  `global`: dedup между всеми rules, использующими этот profile.

- `exact`  
  Проверять точное совпадение после normalization.

### normalization

- `lowercase`  
  Приводить к lower-case.

- `collapse_spaces`  
  Схлопывать последовательности whitespace в один пробел.

- `trim_punctuation`  
  Убирать базовую пунктуацию по краям.

- `replace_yo`  
  Заменять `ё/Ё` на `е/Е` перед lower-case.

### prefix_limit

- `enabled`  
  Включить ограничение одинакового начала.

- `words`  
  Сколько первых слов брать как prefix key.

- `max_count`  
  Сколько accepted-текстов с таким prefix допустимо.

### ngram_similarity

- `enabled`  
  Включить near-duplicate фильтр.

- `ngram`  
  Размер символьной n-gram.

- `threshold`  
  Порог Jaccard similarity. Если similarity >= threshold, кандидат отклоняется.

- `max_compare`  
  Сколько последних accepted-текстов держать для сравнения.
  Это ограничивает стоимость проверки.

Если `dedup_profiles` не задан, engine создает дефолтный `smart_text`.

## callbacks

Глобальные callbacks:

```yaml
callbacks:
  pre_extension:
    - path: "./examples/callbacks.py"
      function: "add_workplace_hint"
  post_validation:
    - path: "./examples/callbacks.py"
      function: "reject_placeholder_text"
```

Rule-level callbacks:

```yaml
rules:
  - id: "crm"
    callbacks:
      pre_extension: []
      post_validation: []
```

Global callbacks выполняются перед rule-level callbacks.

### PreExtensionCallback

Контракт без anchor:

```python
def callback(prompt: str) -> str:
    return prompt
```

Контракт с anchor:

```python
def callback(prompt: str) -> tuple[str, str]:
    return prompt, "case_id"
```

Назначение: изменить уже отрендеренный user prompt перед API-вызовом.
Anchor нужен, когда pre-callback выбирает внешний payload, а post-callback
должен проверить именно этот payload.

Ограничения:

- принимает ровно prompt text;
- возвращает prompt text или пару `(prompt text, anchor)`;
- не получает rule/config/context;
- если возвращает неправильный тип, engine падает с ошибкой callback-а;
- за один prompt поддерживается только один distinct anchor.

### PostValidationCallback

Контракт без anchor:

```python
def callback(text: str) -> tuple[bool, str]:
    return True, ""
```

Контракт с anchor:

```python
def callback(text: str, anchor: str) -> tuple[bool, str]:
    return True, ""
```

Назначение: доменная проверка готового текста после built-in checks.

Правила:

- `True, ""` — принять и идти дальше к dedup;
- `False, "reason"` — отклонить с причиной;
- reason должен быть короткой machine-readable строкой.
- если pre-callback вернул anchor, engine вызовет post-callback как
  `callback(text, anchor)`;
- если pre-callback не вернул anchor, engine вызовет post-callback как
  `callback(text)`.

## rules

```yaml
rules:
  - id: "crm_mentions"
    count: 2000
    batch_size: 16
    diversity_profile: "business_ru"
    dedup_profile: "smart_text"
    goal: "Короткие естественные русские фразы с обязательным упоминанием CRM."
    examples:
      positive: []
      negative: []
    checks: []
    callbacks:
      pre_extension: []
      post_validation: []
```

Поля:

- `id`  
  Обязательный идентификатор rule.
  Используется в `report.json`, JSONL-records и имени `per_rule/<id>.jsonl`.
  Код требует regex `[A-Za-z0-9_.-]+`; практически лучше использовать `[a-z0-9_]+`.

- `count`  
  Сколько accepted-текстов нужно получить.

- `batch_size`  
  Сколько кандидатов просить у модели за один prompt.
  Это не HTTP batch; это число внутри prompt.

- `diversity_profile`  
  Имя profile из `diversity_profiles`.
  Можно `null` или не указывать.

- `dedup_profile`  
  Имя profile из `dedup_profiles`.
  Дефолт: `smart_text`.

- `goal`  
  Главная текстовая спецификация rule.

- `examples.positive`  
  Примеры хороших результатов.

- `examples.negative`  
  Примеры плохих результатов.

- `checks`  
  Ordered list built-in проверок. Выполняются до `post_validation`.

- `callbacks`  
  Rule-level callbacks.

## Built-In Checks

Все checks задаются как:

```yaml
- type: "check_name"
  ...
```

Checks выполняются по порядку. Первый отказ останавливает обработку кандидата.

### word_count_between

Проверяет количество whitespace-separated слов.

```yaml
- type: "word_count_between"
  min: 4
  max: 14
```

Reasons:

- `word_count_between:too_few_words`
- `word_count_between:too_many_words`

### char_count_between

Проверяет длину строки в символах.

```yaml
- type: "char_count_between"
  min: 20
  max: 140
```

Reasons:

- `char_count_between:too_few_chars`
- `char_count_between:too_many_chars`

### require_contains_any

Текст должен содержать хотя бы один fragment.

```yaml
- type: "require_contains_any"
  values: ["CRM", "Битрикс"]
  case_sensitive: true
```

Fields:

- `values` — обязательный список строк.
- `case_sensitive` — дефолт `true`.

Reason:

- `require_contains_any:missing_required_fragment`

### require_contains_all

Текст должен содержать все fragments.

```yaml
- type: "require_contains_all"
  values: ["номер телефона", "снилс"]
  case_sensitive: false
```

Reason:

- `require_contains_all:missing_required_fragment`

### reject_contains_any

Текст не должен содержать ни один fragment.

```yaml
- type: "reject_contains_any"
  values: ["паспорт", "карта", "cvv"]
  case_sensitive: false
```

Reason:

- `reject_contains_any:forbidden_fragment`

### require_regex_any

Текст должен совпасть хотя бы с одним regex.

```yaml
- type: "require_regex_any"
  patterns:
    - "\\d"
    - "(?i)\\bapi\\b"
```

Reason:

- `require_regex_any:regex_required_pattern_missing`

### reject_regex_any

Текст не должен совпасть ни с одним regex.

```yaml
- type: "reject_regex_any"
  patterns:
    - "(?i)\\bjson\\b"
    - "\\?"
```

Reason:

- `reject_regex_any:forbidden_regex`

### russian_text

Проверяет кириллический контекст и латиницу.

```yaml
- type: "russian_text"
  min_cyrillic_chars: 8
  max_latin_chars: 0
  allow_latin_inside:
    - "CRM"
```

Логика:

1. Из текста удаляются fragments из `allow_latin_inside`.
2. В остатке считается кириллица.
3. В остатке считается латиница.

Reasons:

- `russian_text:not_enough_cyrillic`
- `russian_text:too_much_latin`

### no_digits

Запрещает decimal digits.

```yaml
- type: "no_digits"
```

Reason:

- `no_digits:digits_present`

### require_digits

Требует хотя бы одну decimal digit.

```yaml
- type: "require_digits"
```

Reason:

- `require_digits:digits_missing`

### no_latin

Запрещает латиницу вне разрешенных fragments.

```yaml
- type: "no_latin"
  allow_inside:
    - "CRM"
```

Reason:

- `no_latin:latin_present`

### not_instruction_echo

Отсекает ответы, похожие на echo prompt-а или форматных инструкций.

```yaml
- type: "not_instruction_echo"
  extra_patterns:
    - "(?i)\\bcustom_bad_word\\b"
```

Проверяет:

- markdown/list item начало;
- multiline;
- слова вроде `json`, `markdown`, `output`, `format`, `return`, `prompt`,
  `instruction`, `rule`, `example`, `generate`;
- русские фрагменты вроде `сгенерируй`, `верни`, `формат`, `инструкц`;
- дополнительные `extra_patterns`.

Reasons:

- `not_instruction_echo:list_item_echo`
- `not_instruction_echo:multiline_echo`
- `not_instruction_echo:instruction_echo`

## Dedup Rejection Reasons

Dedup reasons пишутся как:

- `dedup:duplicate_exact`
- `dedup:prefix_overuse`
- `dedup:ngram_near_duplicate`

## report.json

`report.json` — единственный mutable JSON status/report.

Структура:

```json
{
  "run_name": "demo",
  "status": "running",
  "model": "example-model",
  "started_at_unix": 1710000000.0,
  "updated_at_unix": 1710000010.0,
  "finished_at_unix": null,
  "totals": {
    "target": 2500,
    "accepted": 100,
    "remaining": 2400
  },
  "rules": {
    "crm_mentions": {
      "rule_id": "crm_mentions",
      "target": 2000,
      "status": "running",
      "accepted": 100,
      "remaining": 1900,
      "api_requests": 20,
      "parsed_candidates": 250,
      "rejected": {
        "dedup:duplicate_exact": 10
      },
      "errors": {
        "api_error": 1
      },
      "rejection_samples": [
        {
          "reason": "require_contains_any:missing_required_fragment",
          "text": "..."
        }
      ],
      "started_at_unix": 1710000000.0,
      "updated_at_unix": 1710000010.0,
      "finished_at_unix": null
    }
  }
}
```

Top-level statuses:

- `pending`
- `running`
- `done`
- `finished_with_incomplete_rules`
- `failed`

Rule statuses:

- `pending`
- `running`
- `done`
- `request_limit_reached`
- `empty_cycle_limit_reached`

## dataset.jsonl And per_rule/*.jsonl

Каждая accepted запись имеет структуру:

```json
{
  "rule_id": "crm_mentions",
  "text": "Проверь, появился ли лид в CRM после звонка.",
  "meta": {
    "run_name": "demo_openai_compatible_generation",
    "source": "openai_compatible_api",
    "model": "example-model",
    "accepted_at_unix": 1710000000.0,
    "request_index": 1,
    "candidate_index": 3,
    "parser": "json_array",
    "diversity": {
      "scenario": ["сообщение в рабочем чате"],
      "style": ["деловой"]
    },
    "callback_anchor": null,
    "callbacks": {
      "pre_extension": [
        {
          "path": "/abs/path/examples/callbacks.py",
          "function": "add_workplace_hint"
        }
      ],
      "post_validation": []
    }
  }
}
```

Fields:

- `rule_id`  
  Rule that accepted the text.

- `text`  
  Final accepted text. Output schema is always text-only.

- `meta.run_name`  
  Run name from config.

- `meta.source`  
  Always `openai_compatible_api`.

- `meta.model`  
  API model name.

- `meta.accepted_at_unix`  
  Unix timestamp of acceptance.

- `meta.request_index`  
  API request index inside the rule.

- `meta.candidate_index`  
  Candidate index inside parsed response.

- `meta.parser`  
  Parser type used for the response.

- `meta.diversity`  
  Sampled diversity context for the prompt that produced the text.

- `meta.callback_anchor`  
  Anchor returned by pre-callback, or `null`.

- `meta.callbacks`  
  Callback specs applied to the prompt/text.

`dataset.jsonl` contains all accepted records.  
`per_rule/<rule_id>.jsonl` contains only records accepted by that rule.

## Resume Semantics

With `run.resume: true`:

- engine reads existing `per_rule/<rule_id>.jsonl`;
- accepted count starts from the number of valid existing rows;
- dedup state is restored from existing rows;
- new rows are appended to `dataset.jsonl` and `per_rule/<rule_id>.jsonl`.

With `run.resume: false`:

- `dataset.jsonl` is truncated;
- all configured `per_rule/<rule_id>.jsonl` files are truncated;
- run starts from zero.

## Minimal Rule Example

```yaml
rules:
  - id: "short_ru"
    count: 100
    goal: "Короткие русские бытовые фразы."
    checks:
      - type: "word_count_between"
        min: 3
        max: 10
      - type: "russian_text"
        min_cyrillic_chars: 6
        max_latin_chars: 0
      - type: "not_instruction_echo"
```

## Anchor Rule Example

```yaml
rules:
  - id: "crm_mentions"
    count: 1000
    goal: "Фразы с точным упоминанием CRM."
    checks:
      - type: "require_contains_any"
        values: ["CRM"]
        case_sensitive: true
      - type: "russian_text"
        min_cyrillic_chars: 8
        max_latin_chars: 0
        allow_latin_inside: ["CRM"]
```

## Regex Rule Example

```yaml
rules:
  - id: "numbers"
    count: 1000
    goal: "Фразы с числовыми форматами."
    checks:
      - type: "require_regex_any"
        patterns:
          - "\\d"
      - type: "reject_regex_any"
        patterns:
          - "(?i)\\bjson\\b"
```

## Callback Rule Example

```yaml
rules:
  - id: "custom_domain"
    count: 100
    goal: "Фразы, которые проверяются внешней доменной логикой."
    callbacks:
      pre_extension:
        - path: "./examples/callbacks.py"
          function: "add_workplace_hint"
      post_validation:
        - path: "./examples/callbacks.py"
          function: "reject_placeholder_text"
```
