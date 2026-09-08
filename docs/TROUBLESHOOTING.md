# Solução de problemas

## 1. Rode o diagnóstico

No Windows:

```text
DIAGNOSTICO.bat
```

Depois confira `data/logs/baixai-forge.log`.

## 2. "Python não encontrado"

Instale Python 3.11+ e marque **Add Python to PATH**. Feche e abra novamente o Prompt/Explorer antes de rodar o instalador.

## 3. FFmpeg não encontrado

O Baixaí Forge abre sem FFmpeg, mas MP3 e vários vídeos que precisam unir áudio + vídeo não funcionarão.

Instale os binários `ffmpeg` e `ffprobe` e confirme:

```text
ffmpeg -version
ffprobe -version
```

Não confunda o executável FFmpeg com pacotes Python de nome parecido.

## 4. Um site parou de funcionar

Atualize primeiro o yt-dlp:

```text
ATUALIZAR_YTDLP.bat
```

Sites alteram páginas/APIs com frequência e os extractors precisam acompanhar.

## 5. YouTube pede componentes JavaScript

Versões atuais do yt-dlp recomendam `yt-dlp-ejs` e um runtime JavaScript suportado para suporte completo ao YouTube. O requisito `yt-dlp[default]` instala os componentes Python recomendados; instale também Deno ou Node.js quando o diagnóstico indicar ausência de runtime.

## 6. Conteúdo exige login

Configure `BAIXAI_COOKIES_FILE` ou `BAIXAI_COOKIES_BROWSER` no `.env`. Use somente sua própria sessão e conteúdo que você possa acessar legitimamente.

## 7. Erro 403 / 429

- atualize o yt-dlp;
- aguarde se houver rate limiting;
- confirme se o conteúdo abre normalmente no navegador;
- se o conteúdo exigir sessão, configure cookies;
- não tente contornar bloqueios de acesso que você não tem autorização para ultrapassar.

## 8. Job ficou "Interrompido"

Isso ocorre quando o app foi fechado/reiniciado durante um job. Use **Tentar novamente**. O estado não é perdido porque o histórico fica no SQLite.

## 9. Porta 8765 ocupada

Crie `.env` e altere:

```env
BAIXAI_PORT=8766
```

## 10. Quero usar outra pasta de downloads

```env
BAIXAI_DOWNLOAD_DIR=D:\Downloads\BaixaiForge
```

Garanta permissão de escrita e espaço livre suficiente.


## Link curto da Shopee retorna `Unsupported URL`

A partir da v1.1.0 o Baixaí Forge não envia links `br.shp.ee` diretamente ao extrator genérico do yt-dlp. Ele resolve o redirecionamento da Shopee, abre a página `sv.shopee.com.br/share-video/...`, lê o payload `__NEXT_DATA__` e localiza o MP4 do CDN.

Se ainda falhar:

1. execute `ATUALIZAR_YTDLP.bat`;
2. confirme que o link abre normalmente no navegador;
3. verifique `data/logs/baixai-forge.log`;
4. tente novamente alguns minutos depois se a Shopee estiver limitando requisições.

Uma mudança estrutural no HTML/JSON da Shopee pode exigir atualização do resolvedor `baixai_forge/shopee.py`.
