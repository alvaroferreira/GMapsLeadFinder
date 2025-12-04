# language: pt

Funcionalidade: Gestao de Pipeline com Kanban
  Como um utilizador do Geoscout Pro
  Quero gerir o status dos meus leads num pipeline Kanban
  Para organizar e acompanhar o progresso das vendas

  Contexto:
    Dado que tenho um servico de leads configurado
    E tenho leads de exemplo na base de dados

  Cenario: Transicao de status bem-sucedida
    Dado que tenho um lead com status "new"
    Quando atualizo o status para "contacted"
    Entao o lead deve ter status "contacted"
    E o campo last_updated_at deve ser atualizado
    E a transicao deve ser persistida na base de dados

  Cenario: Atribuicao de tags multiplas
    Dado que tenho um lead sem tags
    Quando adiciono as tags "premium", "tech", "urgente"
    Entao o lead deve ter as 3 tags atribuidas
    E as tags devem estar na ordem correta
    E as tags devem ser guardadas como lista JSON

  Cenario: Adicionar notas ao lead
    Dado que tenho um lead com id "bdd_place_001"
    Quando adiciono a nota "Cliente interessado em pacote premium"
    Entao a nota deve ser adicionada com timestamp
    E as notas existentes devem ser preservadas
    E o formato deve ser "[YYYY-MM-DD HH:MM] texto"

  Cenario: Erro - Status invalido
    Dado que tenho um lead com id "bdd_place_001"
    Quando tento atualizar o status para "invalid_status"
    Entao devo receber um erro de validacao
    E a mensagem deve indicar status invalido
    E o lead deve manter o status original

  Cenario: Erro - Lead nao encontrado
    Quando tento atualizar um lead com id "lead_inexistente"
    Entao devo receber um erro de lead nao encontrado
    E a mensagem deve conter o ID do lead
    E nenhuma atualizacao deve ser realizada

  Cenario: Concorrencia - Duas atualizacoes simultaneas
    Dado que tenho um lead com id "bdd_place_002"
    E carrego o lead em duas sessoes diferentes
    Quando atualizo o lead na primeira sessao
    E atualizo o lead na segunda sessao
    Entao ambas as atualizacoes devem ser aplicadas
    E o last_updated_at deve refletir a ultima atualizacao

  Cenario: Filtrar leads por status
    Dado que tenho leads com varios status
    Quando filtro leads por status "qualified"
    Entao devo receber apenas leads qualificados
    E a contagem deve corresponder aos leads filtrados
    E leads com outros status devem ser excluidos

  Cenario: Filtrar leads por score minimo
    Dado que tenho leads com varios scores
    Quando filtro leads por score minimo 70
    Entao devo receber apenas leads com score >= 70
    E todos os resultados devem cumprir o criterio
    E leads com score inferior devem ser excluidos

  Cenario: Filtrar leads por tags
    Dado que tenho leads com tags diferentes
    Quando filtro leads pela tag "premium"
    Entao devo receber apenas leads com tag "premium"
    E leads sem essa tag devem ser excluidos
