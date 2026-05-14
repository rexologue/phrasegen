# phone_extraction

Этот generation-pack делает датасет для задачи извлечения российского
телефонного номера из шумного окна `PHONE_CAPTURE`.

## Два Шага

Сначала детерминированно генерируются номера и варианты диктовки:

```bash
python -m generations.phone_extraction.build_cases \
  --count 10 \
  --output generations/phone_extraction/out/cases.jsonl \
  --seed 42
```

Для каждого номера создается 11 вариантов:

- 1 полный идеальный;
- 5 полных шумных;
- 5 намеренно неполных.

Итого для `N` номеров:

```text
(1 + 5 + 5) * N = 11N variants
```

Затем запускается основной генератор, который через callbacks берет эти
варианты и просит LLM завернуть их в реалистичные реплики.

```bash
export OPENAI_API_KEY="..."
export PHONE_EXTRACTION_CASES_PATH="$PWD/generations/phone_extraction/out/cases.jsonl"
export PHONE_EXTRACTION_USED_PATH="$PWD/generations/phone_extraction/out/used.jsonl"
export PHONE_EXTRACTION_ACCEPTED_PATH="$PWD/generations/phone_extraction/out/accepted_mapping.jsonl"

python generate.py --config generations/phone_extraction/config.yaml
```

## Номер

Канонический номер:

```text
8 XXX XXX XX XX
```

Генерация блоков:

- первый блок всегда `8`;
- следующий трехзначный блок по умолчанию `800..999`;
- следующий блок `000..999`, fixed-width, поэтому бывают `009`, `042`;
- последние блоки `00..99`, fixed-width, поэтому бывают `03`, `05`, `00`.

`phone_digits` всегда ровно 11 цифр и начинается с `88` или `89`.

Диапазон второго блока можно переопределить:

```bash
python -m generations.phone_extraction.build_cases \
  --count 10 \
  --output generations/phone_extraction/out/cases.jsonl \
  --operator-min 900 \
  --operator-max 999
```

## Варианты

Каждая строка `cases.jsonl`:

```json
{
  "case_id": "phone_000001__complete_noisy_1",
  "phone_digits": "89816540394",
  "target_digits": "89816540394",
  "expected_result": "89816540394",
  "kind": "complete_noisy",
  "variant_index": 1,
  "blocks": ["8", "981", "654", "03", "94"],
  "spoken": "+7 девятьсот восемьдесят один 654 ноль три девяносто четыре",
  "notes": ["noise_1"]
}
```

Для неполных вариантов:

- `expected_result: null`;
- `target_digits` содержит намеренно неполный номер или номер без префикса.

## Incomplete Варианты

Создаются 5 видов:

- нет первого блока `8`, но есть остаток;
- есть только `8`;
- есть `8 XXX`;
- есть `8 XXX XXX`;
- есть `8 XXX XXX XX`.

Это покрывает правило: нельзя достраивать отсутствующий префикс или хвост.

## Callbacks

`inject_phone_case(prompt)`:

- читает `PHONE_EXTRACTION_CASES_PATH`;
- читает/обновляет `PHONE_EXTRACTION_USED_PATH`;
- выбирает следующий case по кругу;
- добавляет case в prompt;
- возвращает `(prompt, case_id)`.

Конкретный номер не подставляется в `prompts/user.md` через placeholder.
Сначала ядро заполняет стандартные placeholders вроде `{goal}`, `{checks}`,
`{output_contract}`. Потом `inject_phone_case` добавляет phone-specific блок
из `cases.jsonl`. Это позволяет гонять variants по кругу и передавать `case_id`
в post-callback через anchor.

`validate_phone_case_output(text, anchor)`:

- получает `case_id` через anchor;
- проверяет, что исходная диктовка присутствует в LLM-реплике;
- проверяет, что полный канонический номер не утек цифрами;
- пишет accepted mapping в `PHONE_EXTRACTION_ACCEPTED_PATH`.

## Accepted Mapping

Каждая успешная LLM-реплика дополнительно пишется в
`accepted_mapping.jsonl`:

```json
{
  "case_id": "phone_000001__complete_ideal_0",
  "phone_digits": "89816540394",
  "target_digits": "89816540394",
  "expected_result": "89816540394",
  "kind": "complete_ideal",
  "spoken": "восемь девятьсот восемьдесят один ...",
  "llm_text": "Клиент: записывайте, восемь ..."
}
```

Для неполных вариантов `expected_result` будет `null`, а `target_digits`
будет подномером.
