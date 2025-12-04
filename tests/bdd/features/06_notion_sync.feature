# language: pt
Funcionalidade: Sincronização com Notion CRM
  Como utilizador do Geoscout Pro
  Quero sincronizar os meus leads com o Notion
  Para gerir contactos num CRM centralizado

  Contexto:
    Dado que tenho uma base de dados de teste
    E que tenho 3 leads na base de dados

  Cenário: Configuração e teste de conexão bem-sucedida
    Dado que tenho uma API key válida do Notion
    Quando testo a conexão com o Notion
    Então a conexão deve ser bem-sucedida
    E devo receber informação do workspace

  Cenário: Listar databases e selecionar alvo
    Dado que tenho uma API key válida do Notion
    E que o Notion tem 2 databases disponíveis
    Quando listo as databases disponíveis
    Então devo receber 2 databases
    E cada database deve ter id e título

  Cenário: Sincronização inicial cria pages no Notion
    Dado que o Notion está configurado com database válida
    E que tenho 3 leads não sincronizados
    Quando sincronizo os 3 leads com o Notion
    Então 3 pages devem ser criadas no Notion
    E os leads devem ter notion_page_id preenchido
    E o campo notion_synced_at deve estar atualizado

  Cenário: Sincronização incremental atualiza apenas alterados
    Dado que o Notion está configurado com database válida
    E que tenho 1 lead já sincronizado com notion_page_id
    E que altero o status do lead para "qualified"
    Quando sincronizo o lead com o Notion
    Então a page existente deve ser atualizada
    E nenhuma page nova deve ser criada
    E o campo notion_synced_at deve ser atualizado

  Cenário: Tratamento de erro - API key inválida
    Dado que tenho uma API key inválida do Notion
    Quando testo a conexão com o Notion
    Então a conexão deve falhar
    E devo receber erro de autenticação

  Cenário: Tratamento de erro - Database não acessível
    Dado que o Notion está configurado com database inválida
    E que tenho 1 lead não sincronizado
    Quando sincronizo o lead com o Notion
    Então a sincronização deve falhar
    E o lead não deve ter notion_page_id
    E devo receber mensagem de erro específica

  Cenário: Idempotência - Sincronizar 2x não duplica
    Dado que o Notion está configurado com database válida
    E que tenho 1 lead não sincronizado
    Quando sincronizo o lead com o Notion pela primeira vez
    E sincronizo o mesmo lead com o Notion novamente
    Então apenas 1 page deve existir no Notion
    E a segunda sincronização deve ser update

  Cenário: Rate limiting Notion respeitado
    Dado que o Notion está configurado com database válida
    E que tenho 10 leads não sincronizados
    Quando sincronizo os 10 leads em batch com concurrency 3
    Então as requisições devem respeitar o rate limit
    E deve haver delay entre cada requisição
    E todas as 10 pages devem ser criadas com sucesso
