# Guia de Integração das Correções de Arquitetura

Este documento fornece instruções passo-a-passo para integrar as correções de arquitetura na aplicação.

---

## 1. Integrar API RESTful no Server Principal

### Passo 1.1: Adicionar router ao server.py

Abrir `/src/web/server.py` e adicionar no topo (depois dos imports):

```python
from src.api.routers import api_v1
```

Adicionar depois da criação do app (linha ~32):

```python
# Incluir API Router v1
app.include_router(api_v1)
```

### Passo 1.2: Remover endpoints JSON antigos

Os seguintes endpoints podem ser removidos de `server.py` (agora estão em `routers.py`):

- `/api/stats` (linha ~1141)
- `/api/leads` (linha ~1148)
- `/api/enrichment/stats` (linha ~643)
- `/api/notifications/unread` (linha ~853)
- `/api/notion/status` (linha ~1125)

---

## 2. Aplicar Migrations de Base de Dados

### Opção A: Executar Script de Migration

```bash
# Ativar venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Executar migrations
python -m src.database.migrations
```

### Opção B: Integrar no Startup

Adicionar em `/src/web/server.py`, na função `main()` (antes de `uvicorn.run`):

```python
from src.database.migrations import run_migrations

def main():
    """Entry point para o servidor web."""
    # Executar migrations no startup
    print("[Startup] Executando migrations...")
    run_migrations()

    port = int(os.getenv("PORT", 6789))
    # ...resto do código
```

---

## 3. Usar ConfigService em vez de funções locais

### Passo 3.1: Substituir funções de .env

Em `/src/web/server.py`, substituir as funções locais:

**Remover (linhas 862-914):**
```python
def _get_env_file_path() -> Path:
    ...

def _read_env_file() -> dict:
    ...

def _write_env_file(env_vars: dict) -> None:
    ...

def _mask_api_key(key: str) -> str:
    ...
```

**Adicionar no topo:**
```python
from src.services.config_service import ConfigService
```

### Passo 3.2: Atualizar endpoints de settings

**Substituir endpoint `/settings` (linha ~916):**

```python
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Pagina de configuracoes."""
    config_service = ConfigService()
    notion = NotionService()
    notion_config = notion.get_config()
    sync_stats = notion.get_sync_stats()

    # Usar ConfigService
    google_maps_key = config_service.get_api_key("GOOGLE_PLACES_API_KEY") or ""
    openai_key = config_service.get_api_key("OPENAI_API_KEY") or ""
    anthropic_key = config_service.get_api_key("ANTHROPIC_API_KEY") or ""
    gemini_key = config_service.get_api_key("GEMINI_API_KEY") or ""
    default_ai_provider = config_service.get_api_key("DEFAULT_AI_PROVIDER") or ""

    # ... resto igual, mas usar config_service.mask_api_key()
```

**Atualizar endpoint `/settings/api-keys/google-maps` (linha ~961):**

```python
@app.post("/settings/api-keys/google-maps")
async def save_google_maps_key(api_key: str = Form(...)):
    """Guarda a API key do Google Maps no .env."""
    config_service = ConfigService()
    try:
        config_service.update_api_key("GOOGLE_PLACES_API_KEY", api_key)
        return {"success": True}
    except ConfigurationError as e:
        return {"success": False, "error": e.message}
```

---

## 4. (Opcional) Usar LeadsService nos Endpoints

Para melhorar separação de concerns, pode-se refatorar endpoints HTML para usar `LeadsService`.

**Exemplo: Endpoint `/leads/{place_id}/update`**

**Antes:**
```python
@app.post("/leads/{place_id}/update", response_class=HTMLResponse)
async def update_lead(request: Request, place_id: str, status: str = Form(None), notes: str = Form(None)):
    with db.get_session() as session:
        business = BusinessQueries.get_by_id(session, place_id)
        if not business:
            return templates.TemplateResponse(...)
        if status:
            business.lead_status = status
        if notes:
            # ... lógica de notas
    return RedirectResponse(...)
```

**Depois:**
```python
from src.services.leads_service import LeadsService, LeadUpdate
from src.exceptions import BusinessNotFoundError

@app.post("/leads/{place_id}/update", response_class=HTMLResponse)
async def update_lead(request: Request, place_id: str, status: str = Form(None), notes: str = Form(None)):
    service = LeadsService()
    try:
        service.update_lead(
            place_id,
            LeadUpdate(status=status, notes=notes)
        )
    except BusinessNotFoundError:
        return templates.TemplateResponse(
            "partials/error.html",
            {"request": request, "message": "Lead nao encontrado"}
        )
    return RedirectResponse(url=f"/leads/{place_id}", status_code=303)
```

---

## 5. Testar Integrações

### 5.1 Testar API RESTful

```bash
# Iniciar servidor
python -m src.web.server

# Em outro terminal, testar endpoints:

# Stats
curl http://localhost:6789/api/v1/stats

# Lista de leads
curl http://localhost:6789/api/v1/leads?limit=5

# Lead específico
curl http://localhost:6789/api/v1/leads/{PLACE_ID}

# Atualizar status
curl -X PATCH http://localhost:6789/api/v1/leads/{PLACE_ID}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "contacted"}'
```

### 5.2 Verificar Documentação API

Abrir no browser:
```
http://localhost:6789/docs
```

Deve mostrar documentação Swagger com todos os novos endpoints v1.

### 5.3 Verificar Indices da BD

**PostgreSQL:**
```sql
\d+ businesses

-- Deve mostrar os novos indices:
-- idx_enrichment
-- idx_score_status
-- idx_website_score
```

**SQLite:**
```sql
.schema businesses

-- Deve mostrar os indices
```

### 5.4 Testar ConfigService

```python
from src.services.config_service import ConfigService

config = ConfigService()

# Ler API key
key = config.get_api_key("GOOGLE_PLACES_API_KEY")
print(f"API Key: {config.mask_api_key(key)}")

# Validar keys necessárias
validation = config.validate_required_keys([
    "GOOGLE_PLACES_API_KEY",
    "OPENAI_API_KEY"
])
print(validation)
# {'GOOGLE_PLACES_API_KEY': True, 'OPENAI_API_KEY': False}
```

---

## 6. Verificar Quebras de Compatibilidade

### ⚠️ Atenção: Mudanças Breaking

As seguintes mudanças podem quebrar código existente:

#### 6.1 Database Schema

**Campos agora são NOT NULL:**
- `business.lead_status`
- `business.enrichment_status`
- `business.first_seen_at`
- `business.last_updated_at`

**Ação necessária:**
Garantir que ao criar novos `Business`, estes campos têm valores válidos.

#### 6.2 API Endpoints Movidos

**Endpoints que mudaram:**
- `/api/stats` → `/api/v1/stats`
- `/api/leads` → `/api/v1/leads`
- `/api/enrichment/stats` → `/api/v1/enrichment/stats`

**Ação necessária:**
Se houver clientes externos da API, atualizar URLs ou manter endpoints antigos como proxy.

---

## 7. Rollback (Se Necessário)

### Se algo correr mal, pode fazer rollback:

#### 7.1 Reverter Migrations

```python
from src.database.migrations import Migration001_AddConstraintsAndIndexes

with db.get_session() as session:
    migration = Migration001_AddConstraintsAndIndexes()
    migration.down(session)
```

#### 7.2 Remover Ficheiros Novos

```bash
# Remover ficheiros criados
rm src/exceptions.py
rm src/api/routers.py
rm src/services/config_service.py
rm src/services/leads_service.py
rm src/database/migrations.py
```

#### 7.3 Reverter models.py

Usar git:
```bash
git checkout src/database/models.py
```

---

## 8. Checklist de Integração

Usar esta checklist para garantir que tudo está integrado:

- [ ] Router API v1 adicionado ao server.py
- [ ] Migrations executadas com sucesso
- [ ] ConfigService substituiu funções locais de .env
- [ ] Endpoints antigos `/api/*` removidos ou marcados como deprecated
- [ ] Testes manuais da API RESTful passaram
- [ ] Documentação Swagger acessível em `/docs`
- [ ] Índices de BD criados (verificar com SQL)
- [ ] Nenhum erro no startup da aplicação
- [ ] Logs mostram migrations aplicadas
- [ ] Frontend HTML ainda funciona normalmente

---

## 9. Próximos Passos Após Integração

1. **Adicionar Testes Automatizados**
   - Criar `tests/api/test_routers.py`
   - Testar cada endpoint RESTful
   - Testar error handling

2. **Configurar Logging**
   - Adicionar `structlog` ao projeto
   - Configurar logs em JSON para produção

3. **Monitorização**
   - Adicionar health checks completos
   - Configurar métricas (Prometheus/Grafana)

4. **Documentação**
   - Completar docstrings em todos os endpoints
   - Criar guia de integração para clientes da API

---

## Suporte

Se encontrar problemas durante a integração:

1. Verificar logs do servidor
2. Consultar o relatório completo: `ARQUITECTURA_BACKEND_RELATORIO.md`
3. Testar rollback se necessário
4. Reportar issues específicos

---

**Última atualização:** 2025-11-28
**Versão:** 1.0
