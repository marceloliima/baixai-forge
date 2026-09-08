# Contribuindo

Obrigado por contribuir com o Baixaí Forge.

## Ambiente

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
```

## Antes de abrir um PR

```bash
python -m ruff check baixai_forge tests
python -m pytest
```

## Regras

- Não inclua cookies, tokens, URLs privadas, arquivos baixados ou dados pessoais em commits/issues.
- Novas plataformas devem entrar na allow-list somente quando houver justificativa e testes.
- Erros técnicos detalhados vão para log; respostas da API devem continuar seguras e compreensíveis.
- Mudanças de comportamento precisam atualizar README/CHANGELOG quando aplicável.
- Não remova o modo localhost seguro por padrão.

## Commits sugeridos

Use mensagens objetivas, por exemplo:

- `feat: add retry endpoint`
- `fix: handle missing ffmpeg`
- `docs: expand Windows troubleshooting`
- `test: cover URL validation`
