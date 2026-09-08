# API — Baixaí Forge v1.1.0

A documentação interativa OpenAPI fica disponível em `http://127.0.0.1:8765/docs` enquanto o app estiver rodando.

## Endpoints principais

### `GET /api/health`

Diagnóstico do ambiente local: versão, yt-dlp, FFmpeg, runtime JavaScript, disco livre e alertas.

### `GET /api/platforms`

Retorna plataformas e qualidades aceitas.

### `POST /api/jobs`

Cria um download.

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "media_type": "video",
  "quality": "1080"
}
```

Resposta: HTTP `202` com o job criado.

### `GET /api/jobs?limit=25`

Lista os jobs mais recentes.

### `GET /api/jobs/{job_id}`

Retorna um job específico.

### `POST /api/jobs/{job_id}/cancel`

Solicita cancelamento de um job ativo.

### `POST /api/jobs/{job_id}/retry`

Cria um novo job com a mesma URL/formato/qualidade de um job finalizado.

### `DELETE /api/jobs/{job_id}`

Remove metadados e a pasta do job. Jobs ativos devem ser cancelados antes.

### `GET /api/files/{job_id}`

Entrega o arquivo final de um job concluído.
