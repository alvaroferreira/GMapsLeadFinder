# AUDITORIA COMPLETA - GEOSCOUT PRO
**Data:** 28 Novembro 2025
**Produto:** Geoscout Pro (Google Maps Lead Finder)
**Versão:** 1.0.0
**Auditor:** Business Analyst & Product Manager

---

## EXECUTIVE SUMMARY

O Geoscout Pro é uma aplicação web de prospeção B2B baseada em dados do Google Maps e OpenStreetMap. A auditoria identificou um produto **funcional mas com riscos técnicos significativos** que devem ser endereçados antes de escalar.

### ESTADO GERAL DO PRODUTO

| Área | Classificação | Notas |
|------|--------------|-------|
| **Feature Completeness** | ⭐⭐⭐⭐ (4/5) | 8/8 features implementadas, algumas com limitações |
| **User Experience** | ⭐⭐⭐ (3/5) | Interface funcional mas não totalmente responsiva |
| **Technical Debt** | ⭐⭐ (2/5) | 82 testes falhados, 6 módulos com 0% cobertura |
| **Security** | ⭐⭐⭐⭐ (4/5) | Bem implementado após correções recentes |
| **Deployment Readiness** | ⭐⭐⭐⭐ (4/5) | Docker + Railway/Render configurados |

**SCORE GERAL: 3.4/5** - Produto em estado Beta, pronto para early adopters mas não para produção em escala.

---

## 1. ANÁLISE DE FEATURES

### 1.1 Search (Google Maps) - ✅ FUNCIONAL (99% coverage)

**Estado:** Totalmente operacional
**Cobertura de Testes:** 99% (src/services/search.py)
**Funcionalidades:**
- ✅ Pesquisa por texto e localização
- ✅ Filtros avançados (radius, tipo, reviews, website)
- ✅ Filtros de data (descobertos esta semana, intervalo)
- ✅ Deduplicação automática
- ✅ Auto-scoring de leads

**Limitações:**
- ⚠️ Alguns testes de integração falham (13 testes)
- ⚠️ Rate limiting não totalmente testado
- ⚠️ Falta validação de input em alguns campos

**Recomendação:** Prioridade BAIXA - feature sólida, apenas melhorias incrementais.

---

### 1.2 OSM Discovery - ✅ FUNCIONAL (65% coverage)

**Estado:** Funcional com algumas lacunas
**Cobertura de Testes:** 65% (src/services/osm_discovery.py, src/api/overpass.py: 59%)
**Funcionalidades:**
- ✅ Descoberta de novos negócios via OpenStreetMap
- ✅ Filtro por tipo de negócio
- ✅ Geocoding com Nominatim
- ✅ Preview antes de guardar
- ✅ Áreas pré-definidas (Lisboa, Porto, etc)

**Limitações:**
- ⚠️ API Overpass pode ter downtime (dependência externa)
- ⚠️ Sem retry logic robusto
- ⚠️ Health check básico

**Recomendação:** Prioridade MÉDIA - adicionar retry e fallback mechanisms.

---

### 1.3 Pipeline/Kanban - ⚠️ PARCIAL (testes falhados)

**Estado:** Interface implementada mas testes críticos falham
**Testes Falhados:** 2 de 2 testes BDD
**Funcionalidades:**
- ✅ Drag & drop visual (HTMX)
- ✅ 5 estados (New, Contacted, Qualified, Converted, Rejected)
- ❌ Concorrência não testada
- ❌ Filtros por status falham nos testes

**Problemas Críticos:**
```
FAILED tests/bdd/steps/test_pipeline_steps.py::test_concorrencia__duas_atualizacoes_simultaneas
FAILED tests/bdd/steps/test_pipeline_steps.py::test_filtrar_leads_por_status
```

**Recomendação:** Prioridade ALTA - corrigir race conditions antes de produção.

---

### 1.4 Enrichment - ✅ FUNCIONAL (98% coverage)

**Estado:** Excelente implementação
**Cobertura de Testes:** 98% (src/services/enricher.py)
**Funcionalidades:**
- ✅ Enriquecimento individual e batch
- ✅ Múltiplos AI providers (OpenAI, Anthropic, Gemini)
- ✅ Retry logic e rate limiting
- ✅ Status tracking (pending, enriching, completed, failed)
- ✅ Concorrência configurável

**Limitações:**
- ⚠️ Custos de API podem escalar rapidamente
- ⚠️ Falta monitoring de custos por provider

**Recomendação:** Prioridade BAIXA - feature robusta, adicionar cost tracking.

---

### 1.5 Export - ✅ FUNCIONAL (100% coverage)

**Estado:** Perfeita implementação
**Cobertura de Testes:** 100% (src/services/exporter.py)
**Funcionalidades:**
- ✅ CSV, Excel, JSON
- ✅ Formatos CRM (HubSpot, Pipedrive, Salesforce)
- ✅ Filtros na exportação
- ✅ Formatação profissional (Excel com headers coloridos)

**Recomendação:** Sem ação necessária - feature production-ready.

---

### 1.6 Notion Sync - ✅ FUNCIONAL (84% coverage)

**Estado:** Funcional com testes incompletos
**Cobertura de Testes:** 84% (src/services/notion.py)
**Funcionalidades:**
- ✅ Conexão e teste de credenciais
- ✅ Listagem de databases
- ✅ Sync individual e batch
- ✅ Tracking de sync status
- ❌ Testes de settings falham (3 testes)

**Problemas:**
```
FAILED tests/bdd/steps/test_settings_steps.py::test_configurar_notion_database_com_sucesso
FAILED tests/bdd/steps/test_settings_steps.py::test_validar_dependências_entre_configurações
FAILED tests/bdd/steps/test_settings_steps.py::test_erro_ao_tentar_sincronizar_sem_configuração_notion
```

**Recomendação:** Prioridade MÉDIA - corrigir fluxo de configuração.

---

### 1.7 Scheduler/Automation - ⚠️ CRÍTICO (95% coverage mas 11 testes falham)

**Estado:** Código sólido mas testes críticos falham
**Cobertura de Testes:** 95% (src/services/scheduler.py)
**Funcionalidades Implementadas:**
- ✅ Pesquisas agendadas com intervalo configurável
- ✅ Notificações para novos leads
- ✅ Logs de execução
- ✅ Auto-start no servidor
- ❌ 11 de 11 testes BDD falham

**Problemas CRÍTICOS:**
```
FAILED tests/bdd/steps/test_scheduler_steps.py::test_criar_pesquisa_rastreada_bemsucedida
FAILED tests/bdd/steps/test_scheduler_steps.py::test_scheduler_executa_pesquisas_no_intervalo_definido
FAILED tests/bdd/steps/test_scheduler_steps.py::test_notificações_criadas_para_novos_leads_qualificados
FAILED tests/bdd/steps/test_scheduler_steps.py::test_tratamento_de_erro_durante_execução
... (total: 11 testes)
```

**Risco:** Em produção, pesquisas agendadas podem não executar corretamente ou criar notificações duplicadas.

**Recomendação:** Prioridade CRÍTICA - bloquear deploy até resolver testes.

---

### 1.8 Settings - ⚠️ PARCIAL (0% coverage)

**Estado:** Funcional mas sem testes
**Cobertura de Testes:** 0% (src/services/config_service.py)
**Funcionalidades:**
- ✅ Gestão de API keys (Google Maps, OpenAI, Anthropic, Gemini)
- ✅ Masking de keys no UI
- ✅ Toggle para ativar/desativar APIs
- ✅ Escrita segura no .env
- ❌ Zero testes unitários

**Problemas:**
- Manipulação direta do ficheiro .env (anti-pattern)
- Sem validação de formato de API keys
- Sem audit log de mudanças

**Recomendação:** Prioridade ALTA - refatorar para usar variáveis de ambiente + secrets manager.

---

## 2. USER EXPERIENCE

### 2.1 Templates & Interface

**Estatísticas:**
- **Total de Templates:** 16 principais + 8 partials
- **Linhas de HTML:** 4,509 linhas
- **Framework CSS:** Tailwind (via CDN)
- **Interatividade:** HTMX 1.9.10
- **Mapas:** Leaflet 1.9.4

**Qualidade Visual:**
- ✅ Design dark mode profissional
- ✅ Color scheme consistente (custom Tailwind config)
- ✅ Componentes reutilizáveis (partials)
- ✅ Loading indicators (HTMX)
- ✅ Formulários bem estruturados

**Problemas de UX Identificados:**

1. **Mobile Responsiveness - ⚠️ LIMITADA**
   - Viewport meta tag presente ✅
   - Apenas 5 ocorrências de @media queries
   - Tailwind responsive classes subaproveitadas
   - **Teste:** Interface não otimizada para mobile (<768px)

2. **Navegação**
   - ✅ Menu principal claro
   - ⚠️ Falta breadcrumbs em páginas profundas
   - ⚠️ Sem shortcuts de teclado

3. **Feedback ao Utilizador**
   - ✅ HTMX indicators
   - ✅ Error partials
   - ⚠️ Falta toast notifications consistentes
   - ⚠️ Sem undo para ações destrutivas

4. **Acessibilidade**
   - ❌ Não testado com screen readers
   - ❌ Falta atributos ARIA
   - ❌ Contrast ratios não verificados
   - ❌ Sem suporte para keyboard-only navigation

**Recomendação:** Prioridade MÉDIA - melhorar mobile e acessibilidade antes de público geral.

---

## 3. TECHNICAL DEBT

### 3.1 Cobertura de Testes

**Análise Detalhada:**

| Módulo | Cobertura | Linhas Não Testadas | Prioridade |
|--------|-----------|---------------------|------------|
| **src/api/routers.py** | 0% | 126 | 🔴 CRÍTICA |
| **src/database/migrations.py** | 0% | 46 | 🟡 MÉDIA |
| **src/main.py** (CLI) | 0% | 278 | 🟢 BAIXA |
| **src/services/config_service.py** | 0% | 69 | 🔴 ALTA |
| **src/utils/helpers.py** | 0% | 39 | 🟡 MÉDIA |
| **src/web/security.py** | 0% | 96 | 🔴 CRÍTICA |
| **src/web/validators.py** | 0% | 141 | 🔴 ALTA |
| **src/web/optimizations.py** | 30% | 26 | 🟡 MÉDIA |
| **src/utils/cache.py** | 30% | 33 | 🟡 MÉDIA |

**Total:** 57% de cobertura geral (1,496 linhas não testadas de 3,502)

**Testes Falhados:** 82 de 361 testes (23% failure rate)

**Categorias de Falhas:**
- Scheduler/Automation: 11 testes
- Search: 3 testes
- Settings: 3 testes
- Pipeline: 2 testes
- Integration: 63 testes

### 3.2 TODOs/FIXMEs no Código

**Encontrados:** 1 TODO apenas
```python
# src/services/scheduler.py
# TODO: Implementar contagem exata se necessario
```

**Análise:** Código bem limpo, sem technical debt óbvio em comentários.

### 3.3 Código Duplicado

**Padrões Identificados:**

1. **Conversão Business → Dict**
   - Repetido em múltiplas views
   - ✅ Mitigado com `businesses_to_dicts()` helper

2. **Validação de Form Data**
   - Parsing de strings → int repetido
   - ⚠️ Deveria usar Pydantic models

3. **Session Management**
   - Pattern `with db.get_session() as session:` consistente ✅
   - Alguns commits manuais desnecessários

**Recomendação:** Prioridade BAIXA - refactoring incremental.

### 3.4 Dependências Desatualizadas

**Análise de pip list --outdated (primeiras 20):**

| Package | Versão Atual | Versão Latest | Tipo | Risco |
|---------|--------------|---------------|------|-------|
| anthropic | 0.39.0 | 0.75.0 | Major | 🟡 Médio |
| click | 8.1.8 | 8.3.1 | Minor | 🟢 Baixo |
| beautifulsoup4 | 4.13.4 | 4.14.2 | Minor | 🟢 Baixo |
| bcrypt | 4.3.0 | 5.0.0 | Major | 🟡 Médio |
| certifi | 2025.4.26 | 2025.11.12 | Patch | 🟢 Baixo |
| cachetools | 5.5.2 | 6.2.2 | Major | 🟡 Médio |

**Recomendação:** Atualizar dependências críticas (anthropic, bcrypt) antes de produção.

---

## 4. SECURITY

### 4.1 Análise de Segurança (OWASP Top 10)

**Status:** ✅ Bem implementado após auditoria recente (ver RELATORIO_SEGURANCA.md)

**Implementações de Segurança:**

1. **CSRF Protection** ✅
   - Tokens criptográficos
   - Constant-time comparison
   - ⚠️ MAS: src/web/security.py tem 0% cobertura de testes

2. **Security Headers** ✅
   - Content-Security-Policy
   - X-Frame-Options: DENY
   - X-Content-Type-Options: nosniff
   - HSTS em produção
   - Permissions-Policy

3. **Rate Limiting** ✅
   - 100 req/min (geral)
   - 10 req/min (sensitive endpoints)
   - ⚠️ In-memory (não escala em multi-instance)

4. **Input Validation** ⚠️
   - Sanitização HTML presente
   - Place ID validation
   - ⚠️ src/web/validators.py tem 0% testes

5. **API Keys Management** ⚠️
   - Masking no UI ✅
   - Stored em .env ⚠️ (deveria usar secrets manager)
   - Rotation manual

**Problemas Críticos Corrigidos:**
- ✅ API keys expostas removidas
- ✅ CSRF implementado
- ✅ Security headers adicionados

**Riscos Remanescentes:**

| Risco | Severidade | Mitigação Atual | Recomendação |
|-------|------------|-----------------|--------------|
| API keys em .env | 🟡 MÉDIO | .gitignore | Usar AWS Secrets Manager |
| Rate limiting in-memory | 🟡 MÉDIO | Funcional para single instance | Migrar para Redis |
| Sem audit logging | 🟡 MÉDIO | Security.log básico | Centralizar logs (Sentry) |
| Validators não testados | 🔴 ALTO | Nenhuma | Adicionar testes |

### 4.2 Security Score: ⭐⭐⭐⭐ (4/5)

**Justificação:** Segurança bem implementada para fase Beta, mas precisa de hardening para produção em escala.

---

## 5. DEPLOYMENT READINESS

### 5.1 Containerização - ✅ COMPLETA

**Dockerfile:**
- ✅ Multi-stage build otimizado
- ✅ Python 3.11 slim
- ✅ Health check configurado
- ✅ Exposição de PORT dinâmico (Railway)
- ✅ Cleanup de dependências de build

**docker-compose.yml:**
- ✅ Presente e funcional
- ✅ PostgreSQL configurado
- ✅ Variáveis de ambiente

### 5.2 Configuração de Deploy

**Plataformas Suportadas:**

1. **Railway** ✅
   - railway.toml presente
   - Auto-deploy configurado
   - PORT dinâmico suportado

2. **Render** ✅
   - render.yaml presente
   - Blueprint configurado
   - PostgreSQL managed

3. **Docker Manual** ✅
   - Dockerfile production-ready
   - Health check

### 5.3 Documentação

**README.md:** ⭐⭐⭐ (3/5)
- ✅ Instalação clara
- ✅ Comandos CLI documentados
- ✅ Custos API explicados
- ⚠️ Falta troubleshooting
- ⚠️ Sem guia de deployment
- ❌ Sem screenshots

**.env.example:** ✅ Presente e completo
- Todas as variáveis documentadas
- Defaults sensatos
- Avisos de segurança

### 5.4 CI/CD - ❌ AUSENTE

**Problemas:**
- ❌ Sem GitHub Actions
- ❌ Sem testes automáticos no PR
- ❌ Sem linting automático
- ❌ Sem deploy preview

**Impacto:**
- Testes devem ser executados manualmente
- Risco de deploy com testes falhados
- Sem quality gates

**Recomendação:** Prioridade CRÍTICA - implementar CI básico antes de produção.

### 5.5 Deployment Readiness Score: ⭐⭐⭐⭐ (4/5)

**Justificação:** Docker + plataformas configuradas, mas falta CI/CD.

---

## 6. PROBLEMAS CRÍTICOS IDENTIFICADOS

### 🔴 BLOQUEADORES DE PRODUÇÃO

1. **82 Testes Falhados (23% failure rate)**
   - **Impacto:** Funcionalidades core podem falhar em produção
   - **Áreas afetadas:** Scheduler (11), Integration (63), Search (3)
   - **Ação:** FIX ALL antes de deploy

2. **Módulos Críticos sem Testes**
   - **security.py (0%)**: Validação de segurança não testada
   - **validators.py (0%)**: Input validation não validada
   - **config_service.py (0%)**: Settings podem corromper
   - **Ação:** Cobertura mínima de 80% antes de produção

3. **Ausência de CI/CD**
   - **Impacto:** Deploy manual propenso a erros
   - **Risco:** Deploy de código com testes falhados
   - **Ação:** GitHub Actions básico (test + lint)

### 🟡 RISCOS MÉDIOS

4. **Race Conditions no Pipeline**
   - Testes de concorrência falham
   - Múltiplos utilizadores podem corromper estado

5. **Rate Limiting In-Memory**
   - Não funciona com múltiplas instâncias
   - Fácil bypass com múltiplos IPs

6. **API Keys em .env**
   - Rotation manual
   - Sem versionamento seguro

### 🟢 MELHORIAS RECOMENDADAS

7. **Mobile Responsiveness**
   - Interface não otimizada para <768px
   - Impacto limitado para B2B desktop-first

8. **Acessibilidade**
   - Sem ARIA labels
   - Screen reader support ausente

9. **Dependências Desatualizadas**
   - Anthropic 0.39 → 0.75 (breaking changes possíveis)
   - Bcrypt 4.3 → 5.0

---

## 7. QUICK WINS DISPONÍVEIS

### Implementação Rápida (< 1 dia cada)

1. **Adicionar GitHub Actions Básico**
   ```yaml
   - Run pytest
   - Run ruff check
   - Fail PR se testes falharem
   ```
   **Impacto:** Previne deploys quebrados
   **Esforço:** 2 horas

2. **Corrigir Testes de Settings**
   - 3 testes falhados com causa clara
   - **Impacto:** +3 testes passando
   - **Esforço:** 3 horas

3. **Adicionar Breadcrumbs na Navegação**
   - Melhorar UX em páginas profundas
   - **Impacto:** Satisfação do utilizador
   - **Esforço:** 4 horas

4. **Mobile Viewport Improvements**
   - Adicionar classes responsive do Tailwind
   - **Impacto:** Usabilidade em tablet/mobile
   - **Esforço:** 6 horas

5. **Atualizar Dependências Patch**
   - certifi, beautifulsoup4, click
   - **Impacto:** Security patches
   - **Esforço:** 1 hora

**Total Quick Wins:** 16 horas de trabalho = +20% product quality

---

## 8. RISCOS TÉCNICOS

### Matriz de Riscos

| Risco | Probabilidade | Impacto | Severidade | Mitigação |
|-------|---------------|---------|------------|-----------|
| **Deploy com testes falhados** | Alta | Alto | 🔴 CRÍTICO | Implementar CI/CD |
| **Scheduler falha em produção** | Média | Alto | 🔴 CRÍTICO | Corrigir 11 testes |
| **Security bypass (validators)** | Baixa | Alto | 🟡 ALTO | Testar validators |
| **Race condition pipeline** | Média | Médio | 🟡 MÉDIO | Adicionar locks |
| **API costs spike** | Baixa | Médio | 🟡 MÉDIO | Rate limiting + alertas |
| **Mobile UX pobre** | Alta | Baixo | 🟢 BAIXO | Responsive design |

### Debt Score: 6.5/10
- **Técnico:** 4/10 (muitos testes falhados)
- **Segurança:** 8/10 (bem implementado)
- **Manutenibilidade:** 7/10 (código limpo mas sem CI)

---

## 9. RECOMENDAÇÕES ESTRATÉGICAS

### Roadmap Sugerido

#### FASE 1: ESTABILIZAÇÃO (Sprint 1-2) - CRÍTICA
**Objetivo:** Tornar produto deployment-ready

- [ ] Corrigir 82 testes falhados (prioridade: Scheduler, Integration)
- [ ] Adicionar testes para security.py, validators.py (min 80%)
- [ ] Implementar GitHub Actions (test + lint)
- [ ] Migrar API keys para secrets manager (Railway/Render vars)
- [ ] Adicionar transaction rollback em operações críticas

**Critério de Sucesso:** 95%+ testes passando, CI verde

#### FASE 2: HARDENING (Sprint 3-4) - ALTA
**Objetivo:** Production-grade quality

- [ ] Implementar retry logic robusto (OSM, enrichment)
- [ ] Adicionar rate limiting distribuído (Redis)
- [ ] Melhorar error handling (custom exceptions)
- [ ] Adicionar audit logging centralizado
- [ ] Mobile responsive (Tailwind classes)
- [ ] Atualizar dependências críticas

**Critério de Sucesso:** Zero critical bugs, mobile usable

#### FASE 3: ESCALA (Sprint 5-6) - MÉDIA
**Objetivo:** Preparar para growth

- [ ] Database migrations automáticas (Alembic)
- [ ] Monitoring & alerting (Sentry, Datadog)
- [ ] Cost tracking por feature
- [ ] API versioning (v1, v2)
- [ ] Multi-tenancy preparation
- [ ] Performance benchmarks

**Critério de Sucesso:** Suporta 100+ utilizadores concorrentes

#### FASE 4: POLISH (Sprint 7+) - BAIXA
**Objetivo:** Enterprise-ready

- [ ] Acessibilidade (WCAG AA)
- [ ] Internationalization (i18n)
- [ ] White-label support
- [ ] Advanced analytics
- [ ] API pública para integrações

---

## 10. CONCLUSÕES & NEXT STEPS

### Estado Atual do Produto

**Geoscout Pro está em BETA FUNCIONAL** com as seguintes características:

✅ **Pontos Fortes:**
- Features core implementadas e funcionais
- Arquitetura backend sólida (FastAPI + SQLAlchemy)
- Segurança bem implementada (após auditoria)
- Docker + deployment configurado
- Código limpo e bem estruturado (9,392 linhas)
- Cobertura de testes razoável (57% average)

⚠️ **Pontos de Atenção:**
- 23% de testes falhados (82/361)
- Módulos críticos sem testes (security, validators)
- Ausência de CI/CD
- Mobile responsiveness limitada
- Rate limiting não escalável

❌ **Bloqueadores:**
- Testes de Scheduler críticos falhados
- Sem quality gates automáticos
- Validators não testados (risco de security bypass)

### Go/No-Go para Produção

**RECOMENDAÇÃO: NO-GO** (ainda)

**Justificação:**
- Testes falhados podem causar data corruption (pipeline)
- Scheduler não confiável (pesquisas agendadas core feature)
- Falta CI pode levar a deploys quebrados

**Timeline Estimado para Go:**
- **Fase 1 (Estabilização):** 2-3 sprints (4-6 semanas)
- **Fase 2 (Hardening):** 2-3 sprints (4-6 semanas)
- **TOTAL:** 8-12 semanas até production-ready

### Prioridades Imediatas (Próximas 2 Semanas)

**Sprint Atual - Focus:**

1. **Corrigir Scheduler** (5 dias)
   - 11 testes críticos
   - Feature core para automation

2. **Implementar CI Básico** (1 dia)
   - GitHub Actions: pytest + ruff
   - Bloquear merge se testes falham

3. **Testar Security Modules** (3 dias)
   - security.py: 80%+ coverage
   - validators.py: 80%+ coverage

4. **Corrigir Integration Tests** (3 dias)
   - 63 testes falhados
   - Identificar root cause

5. **Code Freeze & Regression Testing** (3 dias)
   - Garantir 95%+ testes passando
   - Smoke tests em staging

**Resultado Esperado:** Produto estável, deployment-safe, com CI ativo.

---

## ANEXOS

### A. Métricas do Produto

**Código:**
- Linhas de Python: 9,392
- Linhas de Templates: 4,509
- Total de Módulos: 33
- Ficheiros de Teste: 20+

**Testes:**
- Total de Testes: 361
- Passando: 279 (77%)
- Falhando: 82 (23%)
- Cobertura Média: 57%

**Dependências:**
- Produção: 20 packages
- Desenvolvimento: 11 packages
- Desatualizadas: 18+ packages

**Features:**
- Implementadas: 8/8 (100%)
- Production-Ready: 4/8 (50%)
- Necessitam Correção: 4/8 (50%)

### B. Ficheiros Críticos para Review

1. `src/web/security.py` - 0% cobertura ⚠️
2. `src/web/validators.py` - 0% cobertura ⚠️
3. `src/services/scheduler.py` - 11 testes falhados ⚠️
4. `tests/integration/test_api_endpoints.py` - 63 testes falhados ⚠️
5. `src/services/config_service.py` - 0% cobertura, manipula .env ⚠️

### C. Custos Estimados (Produção)

**Google Places API:**
- Text Search: $32 / 1000 requests
- Estimado: 100 pesquisas/dia = ~$10/mês

**AI Enrichment (opcional):**
- OpenAI GPT-4: ~$0.03 / lead
- Estimado: 500 leads/mês = $15/mês

**Hosting (Railway/Render):**
- Hobby Plan: $5/mês
- Pro Plan: $20/mês (recomendado)

**Total Estimado:** $35-50/mês para early stage

### D. Referências

- [RELATORIO_SEGURANCA.md](./RELATORIO_SEGURANCA.md) - Auditoria de segurança completa
- [ARQUITECTURA_BACKEND_RELATORIO.md](./ARQUITECTURA_BACKEND_RELATORIO.md) - Análise de arquitetura
- [RELATORIO_PERFORMANCE.md](./RELATORIO_PERFORMANCE.md) - Otimizações de performance
- [README.md](./README.md) - Documentação do utilizador

---

**Preparado por:** Business Analyst & Product Manager
**Data:** 28 Novembro 2025
**Versão:** 1.0
**Confidencialidade:** Interno

**Próximo Review:** Após conclusão da Fase 1 (Estabilização)
