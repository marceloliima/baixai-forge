# Changelog

Este projeto segue Semantic Versioning.

## [1.1.0] - 2026-09-08

### Added

- Resolvedor próprio para **Shopee Video**.
- Suporte a links curtos `br.shp.ee` e páginas `sv.shopee.com.br/share-video/...`.
- Extração do MP4 a partir do payload público `__NEXT_DATA__`.
- Derivação segura da variante de CDN sem os dois tokens numéricos finais quando esse padrão estiver presente.
- Validação da variante limpa antes do download e fallback automático para `watermarkVideoUrl`, inclusive se a variante validada falhar durante a transferência.
- Suporte a URLs diretas `*.vod.susercontent.com/...mp4`.
- Metadados Shopee (título, usuário e duração) preservados no histórico quando disponíveis.
- `httpx` como cliente HTTP dedicado ao resolvedor Shopee.

### Changed

- Instalador passa a criar `.env` automaticamente a partir de `.env.example` quando necessário.
- Detecção de Shopee no frontend reconhece subdomínios de `shp.ee` e CDN `vod.susercontent.com`.
- Polling do histórico em estado ocioso reduzido para diminuir ruído no console e uso de recursos.
- Access log do Uvicorn desligado por padrão; `BAIXAI_ACCESS_LOG=1` reativa logs HTTP detalhados.

### Security

- Redirecionamentos do resolvedor Shopee são limitados a domínios permitidos e portas HTTP/HTTPS padrão.
- Resposta HTML da página Shopee tem limite de tamanho antes da análise.

## [1.0.0] - 2026-09-08

### Added

- Primeira versão pública do **Baixaí Forge**.
- Interface web local responsiva.
- Integração com yt-dlp para YouTube, Instagram, TikTok, Facebook e Shopee.
- Vídeo e MP3 com opções de qualidade.
- Fila com concorrência limitada.
- Progresso, velocidade, ETA e pós-processamento.
- Cancelamento cooperativo.
- Retry automático para falhas temporárias.
- Persistência SQLite e recuperação após reinício.
- Retenção/limpeza automática de jobs antigos.
- Diagnóstico de yt-dlp, FFmpeg, ffprobe e runtime JavaScript.
- Validação de URL e proteção de caminho.
- Scripts Windows de instalação, execução, atualização e diagnóstico.
- Testes, lint e GitHub Actions.
- Documentação de arquitetura, segurança, API e troubleshooting.
