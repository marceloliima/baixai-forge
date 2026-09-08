# Política de segurança

## Escopo da v1.1.0

Baixaí Forge foi projetado para uso local em `127.0.0.1`. Não publique a porta diretamente na Internet.

## Controles existentes

- allow-list de domínios suportados;
- apenas HTTP/HTTPS;
- rejeição de credenciais embutidas e portas arbitrárias;
- servidor em loopback por padrão;
- validação de caminho antes de servir arquivos;
- nomes de anexos sanitizados;
- headers `nosniff`, `DENY` e `no-referrer`;
- mensagens públicas de erro separadas dos detalhes registrados em log;
- `.env`, banco, logs e downloads fora do Git via `.gitignore`.

## Cookies

Cookies podem conceder acesso à sua conta. Nunca envie `cookies.txt`, `.env`, banco de dados ou logs para o GitHub. Use apenas cookies da sua própria sessão e somente quando necessário.

## Relato de vulnerabilidade

Ao publicar o repositório, substitua esta seção por um canal privado de contato (GitHub Security Advisories ou e-mail dedicado). Evite abrir publicamente detalhes exploráveis antes de uma correção.

## Se desejar acesso por rede

Antes de definir `BAIXAI_ALLOW_REMOTE=1`, adicione no mínimo:

- autenticação;
- TLS/reverse proxy;
- rate limiting;
- firewall/ACL;
- proteção CSRF conforme a arquitetura de autenticação;
- política de retenção e acesso aos arquivos.
