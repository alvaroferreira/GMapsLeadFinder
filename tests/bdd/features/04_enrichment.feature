# language: pt
Funcionalidade: Enriquecimento de Leads com Web Scraping
  Como utilizador do Geoscout Pro
  Quero enriquecer leads com informação de contacto
  Para poder contactá-los mais facilmente

  Contexto:
    Dado que tenho um lead na base de dados

  Cenário: Enriquecimento bem-sucedido extrai emails
    Dado um lead com website "https://empresa.pt"
    E o website contém os emails "contacto@empresa.pt,info@empresa.pt"
    Quando executo o enriquecimento do lead
    Então os emails extraídos são guardados
    E o email principal é "contacto@empresa.pt"
    E o status de enrichment é "completed"
    E o campo "enriched_at" está preenchido

  Cenário: Filtro de emails falsos é aplicado
    Dado um lead com website "https://empresa.pt"
    E o website contém os emails "noreply@empresa.pt,contacto@empresa.pt,no-reply@test.com"
    Quando executo o enriquecimento do lead
    Então apenas o email "contacto@empresa.pt" é guardado
    E os emails "noreply@empresa.pt,no-reply@test.com" são filtrados
    E o status de enrichment é "completed"

  Cenário: Extração de redes sociais
    Dado um lead com website "https://empresa.pt"
    E o website contém link do LinkedIn "https://linkedin.com/company/empresa"
    E o website contém link do Facebook "https://facebook.com/empresa"
    E o website contém link do Instagram "https://instagram.com/empresa"
    Quando executo o enriquecimento do lead
    Então o LinkedIn "https://linkedin.com/company/empresa" é guardado
    E o Facebook "https://facebook.com/empresa" é guardado
    E o Instagram "https://instagram.com/empresa" é guardado
    E o status de enrichment é "completed"

  Cenário: Tratamento de erro - Website timeout
    Dado um lead com website "https://empresa-lenta.pt"
    E o website demora mais de 10 segundos a responder
    Quando executo o enriquecimento do lead
    Então o status de enrichment é "failed"
    E o campo "enrichment_error" contém "Nao foi possivel aceder ao website"

  Cenário: Tratamento de erro - Website bloqueia scraper
    Dado um lead com website "https://empresa-protegida.pt"
    E o website retorna erro 403
    Quando executo o enriquecimento do lead
    Então o status de enrichment é "failed"
    E o campo "enrichment_error" contém "Nao foi possivel aceder ao website"

  Cenário: Máximo de páginas respeitado
    Dado um lead com website "https://empresa-grande.pt"
    E o website tem 10 páginas importantes
    Quando executo o enriquecimento do lead
    Então apenas 5 páginas são visitadas
    E o campo "pages_scraped" não excede 5

  Cenário: Sem emails encontrados
    Dado um lead com website "https://empresa-sem-email.pt"
    E o website não contém emails
    Quando executo o enriquecimento do lead
    Então o status de enrichment é "completed"
    E o campo "email" está vazio
    E o campo "emails_scraped" está vazio

  Cenário: Priorização de email principal
    Dado um lead com website "https://empresa.pt"
    E o website contém os emails "admin@empresa.pt,info@empresa.pt,contacto@empresa.pt"
    Quando executo o enriquecimento do lead
    Então o email principal é "contacto@empresa.pt"
    E todos os emails são guardados em "emails_scraped"

  Cenário: Lead sem website não é enriquecido
    Dado um lead sem website
    Quando executo o enriquecimento do lead
    Então o status de enrichment é "no_website"
    E o campo "enrichment_error" está vazio
    E o campo "enriched_at" está preenchido

  Cenário: Extração de decisores da página de equipa
    Dado um lead com website "https://empresa.pt"
    E o website tem uma página "/equipa" com "João Silva - CEO"
    E o website tem uma página "/equipa" com "Maria Santos - Diretora Comercial"
    Quando executo o enriquecimento do lead
    Então os decisores são guardados
    E o decisor "João Silva" tem o cargo "CEO"
    E o decisor "Maria Santos" tem o cargo "Diretora Comercial"

  Cenário: Enriquecimento em batch com concorrência
    Dado que tenho 5 leads com websites
    Quando executo o enriquecimento em batch com concorrência 3
    Então todos os 5 leads são enriquecidos
    E o processamento é feito em paralelo
    E o tempo total é inferior ao processamento sequencial
