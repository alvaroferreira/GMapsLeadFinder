# language: pt
Funcionalidade: Export de Leads em Múltiplos Formatos
  Como utilizador do Geoscout Pro
  Quero exportar leads em diferentes formatos
  Para integrar com outras ferramentas e CRMs

  Contexto:
    Dado que tenho leads na base de dados

  Cenário: Export CSV bem-sucedido
    Dado que tenho 10 leads para exportar
    Quando exporto os leads para CSV
    Então um ficheiro CSV é criado
    E o ficheiro contém 10 linhas de dados
    E o ficheiro contém headers em português
    E os caracteres especiais são preservados

  Cenário: Export XLSX com formatação
    Dado que tenho 5 leads para exportar
    Quando exporto os leads para XLSX
    Então um ficheiro XLSX é criado
    E o ficheiro tem uma sheet "Leads"
    E os headers estão formatados em negrito
    E os headers têm cor de fundo azul
    E as colunas têm largura ajustada

  Cenário: Export JSON preserva estrutura completa
    Dado que tenho 3 leads para exportar
    E os leads têm dados de enriquecimento
    Quando exporto os leads para JSON
    Então um ficheiro JSON é criado
    E o JSON contém arrays de emails
    E o JSON contém objetos de redes sociais
    E o JSON contém arrays de decisores
    E a estrutura JSON está bem formatada

  Cenário: Export HubSpot com mapeamento correto
    Dado que tenho 5 leads para exportar
    Quando exporto os leads para formato "hubspot"
    Então um ficheiro CSV HubSpot é criado
    E a coluna "name" é mapeada para "Company name"
    E a coluna "formatted_address" é mapeada para "Street address"
    E a coluna "phone_number" é mapeada para "Phone number"
    E a coluna "website" é mapeada para "Company domain name"

  Cenário: Export Pipedrive com mapeamento correto
    Dado que tenho 5 leads para exportar
    Quando exporto os leads para formato "pipedrive"
    Então um ficheiro CSV Pipedrive é criado
    E a coluna "name" é mapeada para "Name"
    E a coluna "phone_number" é mapeada para "Phone"
    E a coluna "website" é mapeada para "Website"

  Cenário: Export Salesforce com mapeamento correto
    Dado que tenho 5 leads para exportar
    Quando exporto os leads para formato "salesforce"
    Então um ficheiro CSV Salesforce é criado
    E a coluna "name" é mapeada para "Company"
    E a coluna "formatted_address" é mapeada para "BillingStreet"
    E a coluna "phone_number" é mapeada para "Phone"

  Cenário: Export com filtros aplicados
    Dado que tenho 20 leads na base de dados
    E 10 leads têm status "qualified"
    E 5 leads têm score maior que 80
    Quando exporto apenas leads com status "qualified"
    Então o ficheiro contém 10 linhas de dados
    E todos os leads têm status "qualified"

  Cenário: Erro - Sem dados para exportar
    Dado que não tenho leads para exportar
    Quando tento exportar os leads para CSV
    Então nenhum ficheiro é criado
    E recebo uma mensagem de erro

  Cenário: Caracteres especiais são escapados em CSV
    Dado que tenho 1 lead com nome 'Café & Bar "O José"'
    E o lead tem endereço com vírgulas
    Quando exporto os leads para CSV
    Então o ficheiro CSV é criado
    E o nome está corretamente escapado
    E o endereço está corretamente escapado
    E o CSV pode ser lido novamente sem erros

  Cenário: Export com colunas personalizadas
    Dado que tenho 5 leads para exportar
    Quando exporto apenas as colunas "name,website,phone_number"
    Então o ficheiro contém apenas 3 colunas
    E as colunas são "Nome,Website,Telefone"

  Cenário: Export preserva URLs do Google Maps
    Dado que tenho 3 leads para exportar
    E todos têm URLs do Google Maps
    Quando exporto os leads para CSV
    Então os URLs do Google Maps são preservados
    E os URLs são clicáveis

  Cenário: Resumo de export é gerado
    Dado que tenho 15 leads para exportar
    E 10 leads têm website
    E 12 leads têm telefone
    Quando peço o resumo de export
    Então o resumo mostra total de 15 leads
    E o resumo mostra 10 leads com website
    E o resumo mostra 12 leads com telefone
    E o resumo mostra score médio
    E o resumo mostra rating médio

  Cenário: Nome de ficheiro com timestamp
    Dado que tenho 5 leads para exportar
    Quando exporto os leads para CSV sem especificar nome
    Então o ficheiro tem nome "leads_YYYYMMDD_HHMMSS.csv"
    E o timestamp está correto

  Cenário: Export em batch de múltiplos formatos
    Dado que tenho 10 leads para exportar
    Quando exporto para os formatos "csv,xlsx,json"
    Então 3 ficheiros são criados
    E um ficheiro CSV existe
    E um ficheiro XLSX existe
    E um ficheiro JSON existe

  Cenário: Validação de formato CRM inválido
    Dado que tenho 5 leads para exportar
    Quando tento exportar para formato "invalid_crm"
    Então recebo um erro de formato não suportado
    E a mensagem lista os formatos suportados
