# language: pt
Funcionalidade: Gestão de Configurações
  Como administrador do Geoscout Pro
  Quero gerir as configurações do sistema
  Para controlar integrações e funcionalidades

  Contexto:
    Dado que tenho acesso à página de settings

  Cenário: Configurar Google Places API key com sucesso
    Dado que tenho uma Google Places API key válida
    Quando configuro a API key do Google Places
    Então a configuração deve ser guardada no .env
    E a variável de ambiente deve estar atualizada
    E devo receber confirmação de sucesso

  Cenário: Validar formato de API key inválido
    Dado que tenho uma API key com formato inválido "abc123"
    Quando tento configurar a API key do Google Places
    Então a configuração não deve ser guardada
    E devo receber erro de validação de formato

  Cenário: Configurar Notion database com sucesso
    Dado que tenho uma API key válida do Notion
    E que tenho um database_id válido
    Quando configuro a integração Notion
    Então a configuração deve ser guardada na base de dados
    E o campo is_active deve ser True
    E devo ver o workspace_name nas configurações

  Cenário: Ativar e desativar features com toggles
    Dado que a Google Places API está ativa
    Quando desativo a Google Places API via toggle
    Então a variável GOOGLE_PLACES_ENABLED deve ser "false"
    E a API key deve ser preservada
    Quando reativo a Google Places API via toggle
    Então a variável GOOGLE_PLACES_ENABLED deve ser "true"

  Cenário: Validar dependências entre configurações
    Dado que não tenho Google Places API configurada
    Quando tento fazer uma pesquisa de lugares
    Então a operação deve falhar
    E devo receber mensagem "API key não configurada"

  Cenário: Histórico de mudanças em integrações
    Dado que o Notion não está configurado
    Quando configuro a integração Notion
    E depois desconecto a integração Notion
    Então devo poder reconectar novamente
    E a nova configuração deve substituir a anterior

  Cenário: Erro ao tentar sincronizar sem configuração Notion
    Dado que o Notion não está configurado
    E que tenho 1 lead na base de dados
    Quando tento sincronizar o lead com o Notion
    Então a sincronização deve falhar
    E devo receber erro "Notion não configurado ou inativo"

  Cenário: Configurar múltiplos AI providers
    Dado que tenho API keys para OpenAI, Anthropic e Gemini
    Quando configuro os 3 AI providers
    E seleciono "openai" como provider padrão
    Então as 3 API keys devem estar guardadas no .env
    E o DEFAULT_AI_PROVIDER deve ser "openai"
    E posso alternar para "anthropic" posteriormente

  Cenário: Mascaramento de API keys na interface
    Dado que tenho uma API key configurada "AIzaSyDEMO_KEY_12345678"
    Quando visualizo a página de settings
    Então devo ver a key mascarada como "AIzaSyDE••••••••••••"
    E os últimos caracteres não devem estar visíveis

  Cenário: Atualizar API key preservando outras configurações
    Dado que tenho Google Places e OpenAI configurados
    Quando atualizo apenas a API key do Google Places
    Então a nova key do Google Places deve ser guardada
    E a API key do OpenAI deve permanecer inalterada
    E as variáveis ENABLED não devem ser afetadas
