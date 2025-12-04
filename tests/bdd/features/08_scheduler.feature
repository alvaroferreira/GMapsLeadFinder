# language: pt
Funcionalidade: Agendamento Automático de Pesquisas
  Como utilizador do Geoscout Pro
  Quero agendar pesquisas automáticas
  Para descobrir novos leads sem intervenção manual

  Contexto:
    Dado que tenho uma base de dados de teste
    E que o scheduler está inicializado

  Cenário: Criar pesquisa rastreada bem-sucedida
    Dado que tenho parâmetros de pesquisa válidos
    Quando crio uma pesquisa rastreada chamada "Restaurantes Lisboa"
    E query "restaurantes" e localização "Lisboa"
    E intervalo de 24 horas
    Então a pesquisa deve ser guardada na base de dados
    E o campo is_active deve ser True
    E next_run_at deve estar definido para agora
    E notify_on_new deve estar ativo

  Cenário: Scheduler executa pesquisas no intervalo definido
    Dado que tenho 1 pesquisa rastreada ativa
    E que next_run_at está no passado
    Quando o scheduler executa o ciclo de verificação
    Então a pesquisa deve ser executada
    E next_run_at deve ser atualizado para +24 horas
    E last_run_at deve estar atualizado
    E total_runs deve incrementar em 1

  Cenário: Notificações criadas para novos leads qualificados
    Dado que tenho 1 pesquisa rastreada com notify_on_new=True
    E threshold de score mínimo de 50
    Quando a pesquisa descobre 3 novos leads
    Então 1 notificação de resumo deve ser criada
    E a notificação deve conter "3 novos leads"
    E o tipo da notificação deve ser "batch_complete"

  Cenário: Log de execução registra estatísticas
    Dado que tenho 1 pesquisa rastreada ativa
    Quando executo a pesquisa manualmente
    E a pesquisa encontra 5 novos leads
    Então 1 log de automação deve ser criado
    E o log deve ter status "success"
    E total_found deve ser registrado
    E new_found deve ser 5
    E duration_seconds deve estar presente

  Cenário: Tratamento de erro durante execução
    Dado que tenho 1 pesquisa rastreada ativa
    E a API do Google Places está indisponível
    Quando o scheduler tenta executar a pesquisa
    Então um log de erro deve ser criado
    E o status deve ser "failed"
    E error_message deve conter detalhes do erro
    E next_run_at deve ser atualizado mesmo assim

  Cenário: Desativar pesquisa rastreada
    Dado que tenho 1 pesquisa rastreada ativa
    Quando desativo a pesquisa via toggle
    Então is_active deve ser False
    E a pesquisa não deve ser executada no próximo ciclo
    Quando reativo a pesquisa via toggle
    Então is_active deve ser True
    E next_run_at deve ser definido para agora

  Cenário: Estatísticas agregadas de automações
    Dado que tenho 3 pesquisas rastreadas
    E 2 estão ativas e 1 inativa
    E existem 10 logs de execução
    E 5 notificações não lidas
    Quando consulto as estatísticas de automação
    Então total_searches deve ser 3
    E active_searches deve ser 2
    E total_executions deve ser 10
    E unread_notifications deve ser 5

  Cenário: Pesquisa agendada respeitando rate limit
    Dado que tenho 1 pesquisa rastreada ativa
    Quando executo a pesquisa com múltiplos resultados
    Então as chamadas à API devem ter delay
    E não deve exceder 3 requisições por segundo
    E a execução deve completar com sucesso

  Cenário: Executar pesquisa agendada imediatamente
    Dado que tenho 1 pesquisa rastreada ativa
    E next_run_at está agendado para daqui a 20 horas
    Quando executo a pesquisa manualmente via "run now"
    Então a pesquisa deve executar imediatamente
    E next_run_at deve permanecer no agendamento original
    E um log de execução manual deve ser criado

  Cenário: Apagar pesquisa rastreada e seus logs
    Dado que tenho 1 pesquisa rastreada com 5 logs de execução
    Quando apago a pesquisa rastreada
    Então a pesquisa deve ser removida da base de dados
    E os logs devem permanecer para histórico
    E as notificações relacionadas devem permanecer
