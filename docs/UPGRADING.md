# Atualizando da v1.0.0 para v1.1.0

A v1.1.0 não altera o esquema do SQLite, então o histórico existente pode ser mantido.

## Pelo GitHub Desktop

1. Faça uma cópia de segurança da sua pasta atual, se desejar.
2. Extraia `Baixai-Forge-v1.1.0.zip` em uma pasta temporária.
3. Copie os arquivos da v1.1.0 por cima dos arquivos do repositório local.
4. **Não copie/apague** sua pasta `data/` nem seu `.env` pessoal.
5. Abra o GitHub Desktop e revise as alterações.
6. Use o commit:
   - Summary: `feat: add native Shopee Video resolver v1.1.0`
   - Description: `Resolve Shopee short links via __NEXT_DATA__, validates clean CDN MP4 variants, adds fallback handling, quieter logs, tests and installer improvements.`
7. Clique em `Commit to main` e depois `Push origin`.
8. No navegador, crie a Release `v1.1.0` com target `main` e anexe `Baixai-Forge-v1.1.0.zip`.

## Dependência nova

A v1.1.0 adiciona `httpx` como dependência de runtime. Execute `INSTALAR.bat` novamente depois de atualizar para garantir que a nova dependência seja instalada.

## `.env`

Seu `.env` antigo continua válido. O instalador agora cria `.env` automaticamente a partir de `.env.example` somente quando o arquivo ainda não existe.
