# Phrase Generator

Универсальный генератор текстовых датасетов.
Он не зависит от `vLLM` напрямую: генерация идет через любой
OpenAI-compatible Chat Completions API.

Главная граница архитектуры:

```text
Rule      -> что считать валидным текстом
Prompts   -> как просить модель получить такие тексты
Engine    -> как вызывать API, парсить, валидировать, дедупить и писать результат
```

## Структура

```text
generate.py                  # CLI entrypoint
config.example.yaml          # полный пример конфига
CONFIG.md                    # полный справочник по конфигу и output
requirements.txt             # минимальные зависимости
examples/
  callbacks.py               # примеры callback-контрактов
phrasegen/
  api/                       # OpenAI-compatible HTTP client
  callbacks/                 # загрузка и выполнение callbacks
  checks/                    # built-in checks
  config/                    # dataclass-сущности и YAML loader
  dedup/                     # normalization, exact/prefix/ngram dedup
  engine/                    # orchestration runner
  io/                        # JSONL writer и report writer
  parsing/                   # json_array / answer_tags / lines parsers
  prompts/                   # prompt renderer и diversity sampler
  utils/                     # общие текстовые функции
```

## Установка

```bash
pip install -r requirements.txt
```

Внешний API должен поддерживать OpenAI-compatible endpoint:

```text
POST /v1/chat/completions
```

## Запуск

```bash
export OPENAI_API_KEY="..."
python generate.py --config config.example.yaml
```

Если API локальный и ключ не нужен, убери `api_key_env` из конфига или поставь
его в `null`.

## Полный Flow

Для каждого `rule` engine делает:

1. Читает YAML в typed dataclass-сущности.
2. Создает OpenAI-compatible API client.
3. Загружает parser, prompt templates, checks, callbacks и dedup policy.
4. Если `run.resume: true`, читает `per_rule/<rule_id>.jsonl` и восстанавливает:
   - уже принятое количество;
   - exact dedup state;
   - prefix counters;
   - recent n-gram state.
5. Сэмплит `diversity_profile`, если он указан у rule.
6. Рендерит prompt из:
   - `rule.goal`;
   - `rule.examples`;
   - описаний `rule.checks`;
   - sampled diversity;
   - `output_contract_template`.
7. Применяет `PreExtensionCallback`: `prompt -> prompt` или `prompt -> (prompt, anchor)`.
8. Отправляет `system + user` messages в OpenAI-compatible API.
9. Парсит ответ модели выбранным parser-ом.
10. Для каждого кандидата:
    - прогоняет built-in checks;
    - прогоняет `PostValidationCallback`: `text -> tuple[bool, str]` или `text, anchor -> tuple[bool, str]`;
    - прогоняет dedup;
    - пишет accepted record в общий `dataset.jsonl`;
    - пишет accepted record в `per_rule/<rule_id>.jsonl`;
    - обновляет `report.json`.

## Что Такое Rule

`Rule` — инвариантная сущность. Она описывает один целевой срез датасета:

- `id` — идентификатор категории;
- `count` — сколько текстов нужно принять;
- `goal` — что хотим получить;
- `examples` — положительные и отрицательные примеры результата;
- `checks` — жесткие условия приемки;
- `dedup_profile` — политика уникальности;
- `diversity_profile` — способ разнообразить запросы к модели;
- `callbacks` — внешние проверки/расширения, если built-in checks недостаточно.

Rule не описывает:

- API endpoint;
- sampling;
- output paths;
- формат report;
- устройство prompt-шаблонов.

## Output

На выходе всегда создаются только основные артефакты:

```text
out/
  report.json
  dataset.jsonl
  per_rule/
    <rule_id>.jsonl
```

`report.json` — один mutable JSON вместо прежних `stats.json` и
`manifest.json`. Он обновляется по ходу выполнения.

`dataset.jsonl` — общий датасет всех rules.

`per_rule/<rule_id>.jsonl` — отдельный датасет одной rule.

Полная структура output описана в [CONFIG.md](CONFIG.md).

## Callback-Контракты

Pre-extension:

```python
def my_pre_extension(prompt: str) -> str:
    return prompt + "\nAdditional instruction."
```

Pre-extension with anchor:

```python
def my_pre_extension(prompt: str) -> tuple[str, str]:
    case_id = "case_001"
    return prompt + "\nUse case_001.", case_id
```

Post-validation:

```python
def my_post_validation(text: str) -> tuple[bool, str]:
    if "CRM" not in text:
        return False, "missing_crm"
    return True, ""
```

Post-validation with anchor:

```python
def my_post_validation(text: str, anchor: str) -> tuple[bool, str]:
    if anchor not in text:
        return False, "anchor_missing"
    return True, ""
```

Если pre-callback возвращает anchor, post-callbacks в этой rule должны принимать
`text, anchor`. Anchor сохраняется в `meta.callback_anchor`.

## Почему JSON Array По Умолчанию

Default parser — `json_array`, поэтому модель просится вернуть:

```json
[
  "Первая фраза.",
  "Вторая фраза."
]
```

Это надежнее, чем произвольные списки или markdown. Если endpoint плохо
держит JSON, можно переключиться на `answer_tags` или `lines`.

## Документация Конфига

Смотри [CONFIG.md](CONFIG.md). Там описаны:

- все top-level поля;
- все поля `run`, `api`, `sampling`, `output`, `parser`, `prompts`;
- структура `user_template`, доступные placeholders и порядок рендера;
- `diversity_profiles`;
- `dedup_profiles`;
- rule schema;
- все built-in check types;
- callback contracts;
- структура `report.json`;
- структура JSONL-record.
