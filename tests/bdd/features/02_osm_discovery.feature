# language: pt

Funcionalidade: Descoberta de negocios via OpenStreetMap
  Como um utilizador do Geoscout Pro
  Quero descobrir negocios novos via OpenStreetMap
  Para encontrar leads alternativos ao Google Maps

  Contexto:
    Dado que tenho um servico OSM configurado

  Cenario: Descoberta OSM bem-sucedida em area delimitada
    Quando descubro negocios em "lisboa" dos ultimos 7 dias
    Entao devo receber elementos OSM validos
    E os negocios devem ter score OSM calculado
    E os elementos devem ser convertidos para Business
    E os resultados devem ser guardados na base de dados

  Cenario: Mapeamento de tipos OSM para tipos de negocio
    Quando descubro negocios com tipo "cafe" em "porto"
    Entao os tipos OSM devem ser mapeados corretamente
    E o business_type deve corresponder ao amenity OSM
    E os negocios devem ter place_types corretos

  Cenario: Deteccao de duplicatas Google vs OSM
    Dado que ja existe um negocio Google com coordenadas 38.7223,-9.1393
    Quando descubro um negocio OSM nas mesmas coordenadas
    Entao o sistema deve detectar a duplicata potencial
    E deve atualizar o negocio existente
    E nao deve criar um negocio duplicado

  Cenario: Tratamento de erro - Query timeout Overpass
    Dado que tenho um servico OSM com timeout configurado
    Quando tento descobrir negocios em "portugal" dos ultimos 30 dias
    Entao devo receber um erro de timeout da Overpass API
    E nenhum resultado deve ser guardado
    E o erro deve ser registado no resultado

  Cenario: Tratamento de erro - Area muito grande
    Dado que tenho um servico OSM com area muito grande
    Quando tento descobrir negocios em area extensa
    Entao devo receber um erro de area muito grande
    E o resultado deve conter mensagem de erro apropriada

  Cenario: Elementos OSM sem localizacao valida
    Dado que tenho um servico OSM com elementos sem coordenadas
    Quando descubro negocios com localizacoes invalidas
    Entao os elementos sem lat/lon devem ser ignorados
    E apenas elementos validos devem ser processados
    E o resultado deve indicar elementos filtrados
