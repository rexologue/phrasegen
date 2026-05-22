# whats_app

Generation-pack для TTS-фраз с обязательными продуктовыми и техническими
названиями:

- `АИ МОП`
- `AmoCRM`
- `Bitrix`
- `API`
- `WhatsApp`
- `Telegram`
- `Max`

Каждый rule генерирует по `10000` фраз. Общий целевой объем — `70000` строк.

## Запуск

Сначала укажи OpenAI-compatible endpoint и модель в `config.yaml`.

```bash
export OPENAI_API_KEY="..."
python generate.py --config generations/whats_app/config.yaml
```

Если локальному endpoint не нужен ключ, поставь в конфиге:

```yaml
api:
  api_key_env: null
```

## Output

```text
generations/whats_app/out/
  report.json
  dataset.jsonl
  per_rule/
    ai_mop_phrases.jsonl
    amocrm_phrases.jsonl
    bitrix_phrases.jsonl
    api_phrases.jsonl
    whats_app_phrases.jsonl
    telegram_phrases.jsonl
    max_phrases.jsonl
```

## Правила Качества

Фразы должны быть:

- русскими по основному тексту;
- естественными для произнесения в TTS;
- рабочими по смыслу: продажи, поддержка, CRM, интеграции, клиентские чаты;
- без оформления как диалог, список, сценарий или инструкция;
- с точным неизмененным написанием обязательного термина.

`callbacks.py` дополнительно отсекает:

- неправильное количество обязательного термина;
- другие защищенные термины в чужом rule;
- speaker labels, markdown, кавычки, двоеточия и списки;
- канцелярит и prompt-echo;
- очевидно случайные темы;
- неоднозначный `Max` без контекста канала сообщений.
