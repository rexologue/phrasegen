# targeted_phrases

Generation-pack для четырех отдельных наборов TTS-фраз по `4000` строк:

- `sahara_phrases` — фразы с точным словосочетанием `пустыня Сахара`;
- `refuseniks_phrases` — фразы с точным словом `отказников`;
- `question_check_phrases` — фразы, заканчивающиеся на `Окей?`, `Хорошо?`, `Договорились?`, `Алло?` или `Понятно?`;
- `one_c_phrases` — фразы с точным упоминанием `1С`.

## Запуск

Сначала укажи OpenAI-compatible endpoint и модель в `config.yaml`.

```bash
export OPENAI_API_KEY="..."
python generate.py --config generations/targeted_phrases/config.yaml
```

Если локальному endpoint не нужен ключ, поставь в конфиге:

```yaml
api:
  api_key_env: null
```

Можно запускать через скрипт:

```bash
generations/targeted_phrases/run.sh
```

## Output

```text
generations/targeted_phrases/out/
  report.json
  dataset.jsonl
  per_rule/
    sahara_phrases.jsonl
    refuseniks_phrases.jsonl
    question_check_phrases.jsonl
    one_c_phrases.jsonl
```

## Валидация

YAML checks отсекают длину, отсутствие обязательного фрагмента, нерусский
контекст и echo-инструкции. `callbacks.py` дополнительно проверяет точное
написание, одиночное вхождение обязательного фрагмента, отсутствие форматного
мусора и финальную позицию вопросительной постановки.
