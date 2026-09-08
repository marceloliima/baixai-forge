# Arquitetura — Baixaí Forge v1.1.0

## Objetivos

1. Manter o sistema local e simples de instalar.
2. Isolar mudanças frequentes do yt-dlp em uma única camada.
3. Não perder histórico quando o processo reiniciar.
4. Evitar que erros internos e caminhos locais sejam usados de forma insegura.
5. Permitir testes de validação, persistência e regras sem efetuar downloads reais.

## Fluxo

```text
Browser
  |
  v
FastAPI (app.py)
  |
  +--> validação Pydantic + allow-list (models.py / platforms.py)
  |
  v
JobManager (jobs.py)
  |          \
  |           +--> SQLite JobStore (storage.py)
  v
DownloadService (downloader.py)
  |
  v
yt-dlp -> FFmpeg -> data/downloads/<job_id>/arquivo
```

## Decisões

### Persistência SQLite

A versão anterior mantinha jobs apenas em memória. Nesta versão, cada mudança relevante é persistida. Se o programa fechar durante um download, o job reaparece como `interrupted` e pode ser reenviado.

### Uma pasta por job

Cada download usa `data/downloads/<job_id>/`. Isso reduz colisões de nomes e simplifica remoção segura.

### Cancelamento cooperativo

O yt-dlp roda em thread para não bloquear o event loop do FastAPI. Um `threading.Event` é verificado pelos hooks de progresso e pós-processamento. O cancelamento não usa `Task.cancel()` sobre a thread, porque isso poderia deixar processamento ativo sem controle.

### Defesa de caminho

A API nunca aceita um caminho de arquivo vindo do navegador. O caminho final é salvo pelo backend e novamente validado com `Path.relative_to()` antes de ser servido.

### Localhost por padrão

Um downloader sem autenticação não deve ficar exposto acidentalmente em `0.0.0.0`. A configuração falha de forma explícita quando um host remoto é informado sem `BAIXAI_ALLOW_REMOTE=1`.

## Estados do job

`queued -> downloading -> processing -> done`

Fluxos alternativos:

- `downloading -> retrying -> downloading`
- `queued/downloading/processing -> cancelling -> cancelled`
- falha definitiva -> `error`
- reinício inesperado -> `interrupted`

## Limitações conhecidas

- O suporte real de cada site depende dos extractors e das mudanças da plataforma.
- Cancelamento durante a fase inicial de extração pode só ocorrer quando o próximo hook do yt-dlp for executado.
- A versão 1.1.0 não possui autenticação multiusuário; por isso o modo padrão é localhost.


## Resolvedor Shopee Video (v1.1.0)

Links Shopee passam por `baixai_forge/shopee.py` antes do yt-dlp. O fluxo segue redirecionamentos apenas dentro da allow-list Shopee, lê o payload Next.js `__NEXT_DATA__`, localiza `mediaInfo.video.watermarkVideoUrl`, deriva a variante limpa do CDN quando o nome termina em `.TOKEN1.TOKEN2.mp4`, valida essa candidata com uma requisição de faixa e só então entrega a URL direta ao yt-dlp. Se a candidata não responder, o sistema usa a URL original do payload.
