# Baixaí Forge v1.0.0

**Baixaí Forge** é um downloader local com interface web, criado para transformar uma ferramenta simples em um projeto organizado, resiliente e publicável no GitHub.

O navegador é apenas a interface. O processamento acontece no seu próprio computador, por padrão em `127.0.0.1`, usando FastAPI + yt-dlp.

> Use somente em conteúdos públicos ou em conteúdos que você tenha autorização para baixar. Respeite direitos autorais, privacidade e os termos aplicáveis de cada plataforma.

## Recursos da versão 1.0.0

- YouTube, Instagram, TikTok, Facebook e Shopee (quando o extrator do yt-dlp oferecer suporte ao link).
- Vídeo em máxima qualidade, 2160p, 1440p, 1080p, 720p, 480p e 360p.
- MP3 em 320, 256, 192, 128 e 96 kbps.
- Fila com limite configurável de downloads simultâneos.
- Progresso real, velocidade, ETA e etapa de pós-processamento.
- Cancelamento cooperativo e seguro.
- Tentativa automática em falhas temporárias de rede/rate limit.
- Histórico persistente em SQLite.
- Jobs ativos são marcados como interrompidos após reinício e podem ser reenviados.
- Limpeza automática de histórico/arquivos antigos.
- Verificação de espaço livre antes do download.
- Validação de URL por allow-list de domínios suportados.
- Proteção contra acesso de arquivos fora da pasta de downloads.
- Bind em localhost por padrão e bloqueio de exposição remota acidental.
- Logs rotativos em UTF-8.
- Diagnóstico de yt-dlp, FFmpeg, ffprobe e runtime JavaScript.
- Scripts de instalação, atualização e diagnóstico para Windows.
- Testes automatizados e GitHub Actions.
- API documentada automaticamente em `/docs`.

## Requisitos

- Windows 10/11, Linux ou macOS.
- Python 3.11 ou superior.
- **FFmpeg/ffprobe** no PATH: necessário para MP3 e para diversos merges/pós-processamentos.
- Para suporte mais completo do YouTube, mantenha o yt-dlp atualizado e tenha um runtime JavaScript suportado, como Deno ou Node.js.

## Instalação rápida no Windows

1. Extraia o projeto.
2. Instale Python 3.11+ e marque **Add Python to PATH**.
3. Instale FFmpeg e adicione-o ao PATH.
4. Execute `INSTALAR.bat`.
5. Execute `INICIAR_BAIXAI_FORGE.bat`.
6. Acesse `http://127.0.0.1:8765` caso o navegador não abra automaticamente.

O instalador cria `.venv`, atualiza as ferramentas de instalação, instala as dependências e valida as importações.

## Instalação manual

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m baixai_forge
```

## Atualização do yt-dlp

As plataformas mudam com frequência. No Windows, execute:

```text
ATUALIZAR_YTDLP.bat
```

Ou manualmente:

```bash
python -m pip install -U "yt-dlp[default]"
```

## Cookies para conteúdo autenticado

Somente use cookies da sua própria sessão e para conteúdo ao qual você tenha acesso legítimo.

Crie `.env` a partir de `.env.example` e configure uma das opções:

```env
BAIXAI_COOKIES_FILE=C:\caminho\cookies.txt
```

ou:

```env
BAIXAI_COOKIES_BROWSER=chrome
```

O formato completo aceito para navegador acompanha o yt-dlp: `BROWSER[+KEYRING][:PROFILE][::CONTAINER]`.

## Configuração

Copie `.env.example` para `.env`. Principais opções:

| Variável | Padrão | Função |
|---|---:|---|
| `BAIXAI_HOST` | `127.0.0.1` | Host HTTP |
| `BAIXAI_PORT` | `8765` | Porta HTTP |
| `BAIXAI_MAX_CONCURRENT` | `2` | Downloads simultâneos |
| `BAIXAI_JOB_RETRIES` | `1` | Novas tentativas após falha temporária |
| `BAIXAI_RETENTION_HOURS` | `72` | Retenção de jobs finalizados |
| `BAIXAI_SOCKET_TIMEOUT` | `30` | Timeout de rede do yt-dlp |
| `BAIXAI_MIN_FREE_DISK_MB` | `512` | Reserva mínima de espaço livre |
| `BAIXAI_DOWNLOAD_DIR` | `data/downloads` | Pasta de arquivos |
| `BAIXAI_LOG_LEVEL` | `INFO` | Nível de log |
| `BAIXAI_NO_BROWSER` | `0` | `1` desativa abertura automática |

### Exposição remota

O projeto é **local-first**. Se `BAIXAI_HOST` não for loopback, a aplicação se recusa a iniciar, a menos que `BAIXAI_ALLOW_REMOTE=1` seja definido conscientemente. Antes de expor a aplicação em rede, adicione autenticação, TLS e controles de acesso adequados.

## Dados locais

A pasta `data/` é criada automaticamente e não deve ser versionada:

```text
data/
├── baixai-forge.sqlite3
├── downloads/
└── logs/
    └── baixai-forge.log
```

## Desenvolvimento

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check baixai_forge tests
python -m pytest
```

## Estrutura

```text
baixai_forge/
├── app.py             # API/web e proteção HTTP
├── config.py          # configurações e variáveis de ambiente
├── downloader.py      # integração isolada com yt-dlp
├── jobs.py            # fila, retry, cancelamento e manutenção
├── models.py          # modelos de domínio e validação Pydantic
├── platforms.py       # normalização de URL e allow-list
├── storage.py         # persistência SQLite
├── static/            # CSS/JavaScript sem CDN
└── templates/         # interface HTML
```

Veja também `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/API.md` e `docs/TROUBLESHOOTING.md`.

## Licença

MIT. Dependências possuem suas próprias licenças; consulte os projetos correspondentes.
