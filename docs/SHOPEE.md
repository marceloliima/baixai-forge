# Shopee Video — resolvedor próprio (v1.1.0)

O yt-dlp pode cair no extrator genérico para links curtos/páginas do Shopee Video e retornar `Unsupported URL`. O Baixaí Forge v1.1.0 trata Shopee antes do yt-dlp.

## Fluxo

1. valida o link como Shopee (`shp.ee`, `shopee.*` ou CDN `*.vod.susercontent.com`);
2. segue redirecionamentos somente dentro da allow-list Shopee;
3. abre a página pública `sv.shopee.com.br/share-video/...`;
4. lê o JSON do script `__NEXT_DATA__`;
5. obtém `props.pageProps.mediaInfo.video.watermarkVideoUrl`;
6. quando o nome do MP4 termina em `.TOKEN_NUMERICO.TOKEN_NUMERICO.mp4`, deriva a variante sem esses dois tokens;
7. valida a variante derivada com uma requisição de faixa (`Range: bytes=0-0`);
8. se a variante responder, ela é usada; caso contrário, o sistema volta automaticamente para `watermarkVideoUrl`; se a variante falhar já durante o download, o fallback também é tentado;
9. a URL direta é entregue ao yt-dlp, preservando fila, progresso, MP3, cancelamento, retries e histórico.

Exemplo do padrão reconhecido:

```text
.../video.16003551755115279.9253.mp4
                 ↓
.../video.mp4
```

A transformação só é aplicada ao CDN Shopee `*.vod.susercontent.com` e apenas quando os dois sufixos são numéricos e aparecem imediatamente antes de `.mp4`.

## Segurança

O resolvedor não segue redirecionamentos para domínios arbitrários, não aceita portas personalizadas e limita o HTML da página a 5 MiB. Isso evita transformar o recurso de resolução de short links em um proxy HTTP genérico.

## Compatibilidade futura

A estrutura do site da Shopee pode mudar. Por isso o código está isolado em `baixai_forge/shopee.py` e coberto por testes específicos. Se `__NEXT_DATA__` mudar de formato, a correção pode ficar restrita a esse módulo.
