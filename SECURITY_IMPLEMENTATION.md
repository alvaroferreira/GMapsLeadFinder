# Guia de Implementação - Security Fixes

Este documento descreve os passos necessários para integrar as correções de segurança na aplicação Geoscout Pro.

---

## Ficheiros Criados

1. **src/web/security.py** - Módulo de segurança principal
2. **src/web/validators.py** - Validadores Pydantic para inputs
3. **SECURITY.md** - Documentação de segurança completa

## Ficheiros Modificados

1. **.env** - API keys removidas e substituídas por placeholders

---

## Passo 1: Instalar Dependências

Adicione ao `requirements.txt` se ainda não existirem:

```txt
# Security
python-multipart  # Para Form data
itsdangerous      # Para sessions
```

Instalar:
```bash
pip install python-multipart itsdangerous
```

---

## Passo 2: Integrar Security Middleware no server.py

### 2.1. Adicionar Imports

No início de `src/web/server.py`, adicionar:

```python
import secrets
import os
from starlette.middleware.sessions import SessionMiddleware

# Import security modules
from src.web.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    rate_limiter,
    strict_rate_limiter,
    verify_csrf_token,
    get_csrf_token,
    log_security_event,
)
```

### 2.2. Configurar Secret Key

Após a criação do `app`, adicionar:

```python
# SECURITY: Generate or load a secret key for session management
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Add security middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)
```

### 2.3. Modificar Template Context

Modificar a função que renderiza templates para incluir CSRF token:

```python
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Pagina inicial com dashboard."""
    with db.get_session() as session:
        stats = BusinessQueries.get_stats(session)
        recent_searches = SearchHistoryQueries.get_recent(session, limit=5)

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "stats": stats,
                "recent_searches": recent_searches,
                "has_api_key": settings.has_api_key,
                "csrf_token": get_csrf_token(request),  # ADICIONAR ISTO
            },
        )
```

---

## Passo 3: Adicionar CSRF Protection aos Endpoints POST

### Exemplo: Endpoint de Pesquisa

**ANTES**:
```python
@app.post("/search", response_class=HTMLResponse)
async def do_search(
    request: Request,
    query: str = Form(...),
    location: str = Form(""),
    # ...
):
    # código...
```

**DEPOIS**:
```python
@app.post("/search", response_class=HTMLResponse)
async def do_search(
    request: Request,
    csrf_token: str = Form(...),  # ADICIONAR
    query: str = Form(...),
    location: str = Form(""),
    # ...
):
    # ADICIONAR validação CSRF
    verify_csrf_token(request, csrf_token)

    # resto do código...
```

### Endpoints que Precisam de CSRF

Adicionar `csrf_token: str = Form(...)` e `verify_csrf_token(request, csrf_token)` em:

1. `/search` (POST)
2. `/leads/{place_id}/update` (POST)
3. `/leads/{place_id}/status` (POST)
4. `/export/download` (POST)
5. `/enrichment/enrich/{place_id}` (POST)
6. `/enrichment/enrich-batch` (POST)
7. `/automation/create` (POST)
8. `/automation/{tracked_id}/toggle` (POST)
9. `/automation/{tracked_id}/delete` (POST)
10. `/automation/{tracked_id}/run-now` (POST)
11. `/settings/api-keys/google-maps` (POST)
12. `/settings/api-keys/ai` (POST)
13. `/settings/notion/test` (POST)
14. `/settings/notion/connect` (POST)
15. `/settings/notion/disconnect` (POST)
16. `/notion/sync/{place_id}` (POST)
17. `/notion/sync-batch` (POST)
18. `/notifications/{notification_id}/read` (POST)
19. `/notifications/read-all` (POST)
20. `/notifications/{notification_id}/delete` (POST)

---

## Passo 4: Adicionar CSRF Tokens aos Templates HTML

### 4.1. Templates de Formulários

Em **TODOS** os templates com `<form>`, adicionar campo hidden:

```html
<form method="post" action="/endpoint">
    <!-- ADICIONAR ESTA LINHA -->
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

    <!-- resto dos campos -->
    <button type="submit">Submeter</button>
</form>
```

### 4.2. Formulários HTMX

Para formulários que usam HTMX:

```html
<form hx-post="/search"
      hx-target="#search-results"
      hx-indicator="#search-indicator">

    <!-- ADICIONAR ESTA LINHA -->
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

    <!-- resto dos campos -->
</form>
```

### 4.3. Requisições JavaScript Fetch

Para requisições via JavaScript:

```javascript
async function submitForm() {
    const csrfToken = document.querySelector('[name="csrf_token"]').value;

    const response = await fetch('/endpoint', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'csrf_token': csrfToken,
            'field1': value1,
            // ...
        })
    });
}
```

### Templates que Precisam de CSRF Token

1. `search.html` - Formulário de pesquisa
2. `leads.html` - Ações em leads
3. `lead_detail.html` - Atualização de lead
4. `export.html` - Exportação
5. `enrichment.html` - Enriquecimento
6. `automation.html` - Criação de automação
7. `settings.html` - Todos os formulários de settings
8. `notifications.html` - Ações em notificações

---

## Passo 5: Usar Validators Pydantic (Opcional mas Recomendado)

### Exemplo: Endpoint de Pesquisa com Validator

**ANTES**:
```python
@app.post("/search")
async def do_search(
    request: Request,
    query: str = Form(...),
    location: str = Form(""),
    radius: str = Form("5000"),
    # ...
):
    # Parse manual
    radius_int = int(radius) if radius else 5000
    # ...
```

**DEPOIS**:
```python
from src.web.validators import SearchRequest

@app.post("/search")
async def do_search(
    request: Request,
    csrf_token: str = Form(...),
    search_data: SearchRequest = Depends(),
):
    verify_csrf_token(request, csrf_token)

    # Dados já validados e parseados
    result = await service.search(
        query=search_data.query,
        radius=search_data.radius,
        # ...
    )
```

---

## Passo 6: Configurar Variáveis de Ambiente

### 6.1. Gerar Secret Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 6.2. Adicionar ao .env

```bash
# Security
SECRET_KEY=<resultado do comando acima>

# IMPORTANTE: Rotar estas keys se foram expostas!
GOOGLE_PLACES_API_KEY=<sua_nova_key>
OPENAI_API_KEY=<sua_nova_key>
```

### 6.3. Adicionar ao Railway/Heroku

No painel de controlo do Railway:
1. Variables > New Variable
2. Nome: `SECRET_KEY`
3. Valor: <secret key gerado>

---

## Passo 7: Configurar Logging

### 7.1. Verificar Permissões

```bash
touch security.log
chmod 644 security.log
```

### 7.2. Configurar Rotação de Logs (Produção)

Criar `/etc/logrotate.d/geoscout`:

```
/path/to/app/security.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
}
```

---

## Passo 8: Testes de Segurança

### 8.1. Teste Manual de CSRF

```bash
# Tentar POST sem CSRF token
curl -X POST http://localhost:6789/search \
  -d "query=teste"

# Deve retornar 403 Forbidden
```

### 8.2. Teste Manual de Rate Limiting

```bash
# Fazer 110 requisições rápidas
for i in {1..110}; do
  curl http://localhost:6789/
done

# As últimas devem retornar 429
```

### 8.3. Teste de Security Headers

```bash
curl -I http://localhost:6789/

# Verificar presença de:
# Content-Security-Policy
# X-Frame-Options
# X-Content-Type-Options
# etc
```

### 8.4. Teste de Input Validation

Tentar inserir SQL injection:
```bash
curl -X GET "http://localhost:6789/leads/'; DROP TABLE businesses; --"

# Deve retornar 400 Bad Request
```

---

## Passo 9: Deployment em Produção

### Checklist Pré-Deploy

- [ ] Todas as API keys antigas foram rotadas
- [ ] SECRET_KEY está configurado como variável de ambiente
- [ ] CSRF tokens adicionados a todos os formulários
- [ ] Security middleware está ativo
- [ ] Logs de segurança estão a funcionar
- [ ] Testes de segurança passam
- [ ] HTTPS está configurado
- [ ] Backup está configurado

### Comandos de Deploy

```bash
# 1. Commit das alterações
git add src/web/security.py src/web/validators.py SECURITY.md
git commit -m "feat: implement comprehensive security fixes

- Add CSRF protection
- Add security headers middleware
- Add input validation with Pydantic
- Add rate limiting
- Add security logging
- Remove exposed API keys
- Add security documentation"

# 2. Push para produção
git push origin main  # Railway faz deploy automático
```

---

## Passo 10: Monitorização Pós-Deploy

### 10.1. Verificar Logs

```bash
# Local
tail -f security.log

# Railway
railway logs
```

### 10.2. Métricas a Monitorizar

1. **CSRF Failures**: Deve ser ~0 em uso normal
2. **Rate Limit Hits**: Valores normais < 5/dia
3. **Input Validation Errors**: Monitorizar padrões
4. **403/429 Status Codes**: Alertar se > 10/hora

### 10.3. Alertas Recomendados

Configurar alertas para:
- Mais de 10 CSRF failures em 1 hora
- Mais de 100 rate limit hits em 1 hora
- Detecção de SQL injection attempts
- Múltiplas tentativas de XSS

---

## Troubleshooting

### Problema: CSRF token missing

**Erro**: `403 Forbidden - CSRF token validation failed`

**Solução**:
1. Verificar se template tem `{{ csrf_token }}`
2. Verificar se endpoint tem `csrf_token: str = Form(...)`
3. Verificar se SessionMiddleware está ativo

### Problema: Rate limiting a bloquear utilizadores legítimos

**Erro**: `429 Too Many Requests`

**Solução**:
1. Aumentar limite em `security.py`:
```python
rate_limiter = RateLimiter(requests=200, window=60)  # 200 em vez de 100
```

### Problema: CSP a bloquear recursos

**Erro**: `Content Security Policy directive violated`

**Solução**:
1. Ajustar CSP em `SecurityHeadersMiddleware`
2. Adicionar domínios necessários a `script-src` ou `style-src`

### Problema: Secret key diferente entre restarts

**Erro**: Sessions inválidas após restart

**Solução**:
1. Garantir que SECRET_KEY está em variável de ambiente
2. Não usar `secrets.token_urlsafe()` diretamente em produção

---

## Manutenção Contínua

### Revisões Mensais

- [ ] Revisar security.log para padrões suspeitos
- [ ] Atualizar dependências (`pip list --outdated`)
- [ ] Verificar CVEs para bibliotecas usadas
- [ ] Testar backups
- [ ] Revisar configurações de segurança

### Revisões Trimestrais

- [ ] Audit de segurança completo
- [ ] Penetration testing
- [ ] Revisar e atualizar documentação
- [ ] Training de segurança para equipa

---

## Recursos Adicionais

- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

## Suporte

Para questões sobre implementação:
1. Revisar SECURITY.md
2. Consultar este guia
3. Verificar logs de segurança
4. Contactar equipa de segurança

---

**Última atualização**: 2025-11-28
