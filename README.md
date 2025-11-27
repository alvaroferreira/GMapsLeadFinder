# Google Maps Lead Finder

Ferramenta CLI para prospeccao de leads B2B usando a Google Places API.

## Funcionalidades

- Pesquisa de negocios no Google Maps com filtros avancados
- Sistema de Lead Scoring automatico (0-100)
- Base de dados local SQLite para gestao de leads
- Deteccao de novos negocios ao longo do tempo
- Exportacao para CSV, Excel, e formatos CRM (HubSpot, Pipedrive, Salesforce)
- Tracking de pesquisas agendadas

## Instalacao

### Requisitos
- Python 3.11+
- API Key do Google Places

### Setup

```bash
# Clonar/entrar no directorio
cd google-maps-lead-finder

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -e .

# Para desenvolvimento
pip install -e ".[dev]"

# Copiar configuracao
cp .env.example .env
```

### Configurar API Key

1. Ir a [Google Cloud Console](https://console.cloud.google.com/)
2. Criar um projeto ou selecionar existente
3. Ativar a **Places API (New)**
4. Criar credenciais (API Key)
5. Editar `.env` e adicionar a key:

```env
GOOGLE_PLACES_API_KEY=sua_api_key_aqui
```

## Uso

### Pesquisa Basica

```bash
# Pesquisar restaurantes em Lisboa
leadfinder search -q "restaurante Lisboa"

# Com filtros
leadfinder search -q "dentista Porto" --max-reviews 10 --no-website

# Com localizacao especifica (coordenadas)
leadfinder search -q "cafe" -l "38.7223,-9.1393" -r 2000
```

### Listar Leads

```bash
# Todos os leads
leadfinder list

# Filtrar por score minimo
leadfinder list --min-score 50

# Filtrar por status
leadfinder list --status new --limit 50

# Leads sem website
leadfinder list --no-website
```

### Exportar

```bash
# CSV
leadfinder export --format csv

# Excel formatado
leadfinder export --format xlsx

# Para HubSpot
leadfinder export --format hubspot --min-score 40
```

### Ver Novos Negocios

```bash
# Ultimos 7 dias
leadfinder new

# Desde uma data
leadfinder new --since 2024-01-01
```

### Estatisticas

```bash
leadfinder stats
```

### Lead Scoring

```bash
# Recalcular todos os scores
leadfinder score --recalculate

# Explicar score de um lead
leadfinder score --explain PLACE_ID
```

### Tracking Automatico

```bash
# Criar pesquisa agendada
leadfinder track --add "Restaurantes Lisboa" -q "restaurante Lisboa" --interval 24

# Listar pesquisas
leadfinder track --list

# Executar manualmente
leadfinder track --run 1
```

### Gestao

```bash
# Atualizar status de um lead
leadfinder update PLACE_ID --status contacted --notes "Enviado email"

# Backup da base de dados
leadfinder backup

# Ver configuracao
leadfinder config
```

## Lead Scoring

O sistema de scoring (0-100) qualifica leads com base em:

| Criterio | Pontos | Logica |
|----------|--------|--------|
| Sem website | +30 | Precisa de presenca digital |
| Poucos reviews (<10) | +20 | Baixa visibilidade |
| Rating baixo (<4.0) | +15 | Pode precisar de gestao de reputacao |
| Poucas fotos (<5) | +15 | Precisa de conteudo visual |
| Price level alto (3-4) | +10 | Maior budget potencial |
| Tem telefone | +5 | Contactavel |
| Operacional | +5 | Negocio ativo |

**Score mais alto = maior potencial como cliente de marketing digital**

## Estrutura do Projeto

```
src/
├── main.py           # CLI (Click)
├── config.py         # Configuracoes
├── api/
│   ├── google_places.py  # Cliente API
│   └── models.py         # Pydantic models
├── database/
│   ├── db.py         # Conexao SQLAlchemy
│   ├── models.py     # Modelos DB
│   └── queries.py    # Queries
└── services/
    ├── search.py     # Logica de pesquisa
    ├── scorer.py     # Lead scoring
    ├── tracker.py    # Tracking
    └── exporter.py   # Exportacao
```

## Testes

```bash
# Executar todos os testes
pytest

# Com coverage
pytest --cov=src

# Testes especificos
pytest tests/test_scorer.py -v
```

## Custos API

A Google Places API (New) tem os seguintes custos aproximados:

- Text Search: $32 por 1000 requests
- Nearby Search: $32 por 1000 requests

Uma pesquisa completa (60 resultados) faz ~3 chamadas API = ~$0.10

**Recomendacao**: Comecar com budget de $50 para testes.

## Notas Importantes

1. **Termos de Servico Google**: Dados devem ser refreshed a cada 30 dias
2. **RGPD**: Dados sao publicos, mas cuidado com uso em marketing direto na UE
3. **Emails**: A API nao fornece emails (scraping seria uma fase futura)

## Desenvolvimento

```bash
# Instalar deps de dev
pip install -e ".[dev]"

# Linting
ruff check src/

# Type checking
mypy src/
```

## Licenca

MIT
