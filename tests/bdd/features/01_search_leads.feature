# language: pt

Funcionalidade: Pesquisa de Leads no Google Maps
  Como um utilizador do Geoscout Pro
  Quero pesquisar negocios no Google Maps
  Para encontrar novos leads com scoring automatico

  Cenario: Pesquisa bem-sucedida retorna leads com scoring
    Dado que tenho um servico de pesquisa configurado
    Quando pesquiso por "restaurantes Lisboa"
    Entao devo receber resultados da pesquisa
    E os negocios devem ter lead score calculado
    E os resultados devem ser guardados na base de dados

  Cenario: Pesquisa com filtros aplicados corretamente
    Dado que tenho um servico de pesquisa configurado
    E defino filtro de reviews minimo 50
    E defino filtro de rating minimo 4.0
    E defino filtro de tem website como "true"
    Quando pesquiso por "cafes Lisboa" com filtros
    Entao devo receber apenas resultados que cumprem os filtros
    E negocios sem website devem ser filtrados

  Cenario: Tratamento de erro - API key invalida
    Dado que tenho um servico de pesquisa com API key invalida
    Quando tento pesquisar por "restaurantes Porto"
    Entao devo receber um erro de API key invalida
    E nenhum resultado deve ser guardado

  Cenario: Tratamento de erro - Rate limit excedido
    Dado que tenho um servico de pesquisa com rate limit excedido
    Quando tento pesquisar por "clinicas Lisboa"
    Entao devo receber um erro de rate limit
    E nenhum resultado deve ser guardado

  Cenario: Pesquisa retorna resultados vazios
    Dado que tenho um servico de pesquisa configurado
    Quando pesquiso por uma query sem resultados
    Entao devo receber zero resultados
    E a pesquisa deve ser registada no historico

  Cenario: Deduplicacao de negocios repetidos
    Dado que tenho um servico de pesquisa configurado
    E ja existe um negocio "place_001" na base de dados
    Quando pesquiso e encontro o mesmo negocio "place_001"
    Entao o negocio deve ser atualizado
    E nao deve ser criado um negocio duplicado
    E a contagem deve mostrar 0 novos e 1 atualizado
