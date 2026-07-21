# PRD — FitCoach AI
Versão: 1.0 | Data: 2026-04-30

---

## 1. Visão Geral

- **Produto:** FitCoach AI — Plataforma de coaching esportivo inteligente
- **Problema:** Médico sem expertise em educação física precisa prescrever e gerenciar treinos personalizados para múltiplos clientes (ciclismo, musculação, corrida, natação, triathlon), com adaptação automática baseada em dados reais de performance, sem depender de ação manual do cliente.
- **Proposta de Valor:** Um agente IA especializado em medicina do esporte cria, envia e adapta diariamente os planos de treino e orientações nutricionais de cada cliente, integrando automaticamente com Strava, Garmin, TrainingPeaks e Apple Health — sem que o cliente precise fazer nada além de treinar.

### Personas

| Persona | Papel | Necessidades Principais |
|---------|-------|------------------------|
| **Dr. Admin** | Médico administrador da plataforma | Cadastrar clientes, monitorar carteira, visualizar raciocínio da IA, gerar relatórios, gerenciar assinaturas |
| **Agente IA Coach** | Sistema autônomo especializado | Gerar planos por modalidade, analisar carga (TSB), adaptar treinos, criar orientações nutricionais, executar automação diária |
| **Cliente Atleta** | Atleta que recebe e executa treinos | Visualizar treino do dia no celular, conectar plataformas, fornecer feedback, acompanhar evolução |

---

## 2. Objetivos e Critérios de Sucesso

- **Objetivo 1:** Fluxo de automação completo funcionando — cadastro → plano gerado → enviado à plataforma → dados recebidos pós-treino → próximo treino ajustado, sem nenhuma ação manual do cliente
- **Objetivo 2:** Admin consegue gerenciar ≥ 10 clientes simultaneamente no painel
- **Objetivo 3:** Tempo de geração de plano de treino pela IA < 30 segundos por cliente
- **Objetivo 4:** Dados pós-treino importados das plataformas em ≤ 30 minutos após sincronização
- **Objetivo 5:** App carrega treino do dia em < 2 segundos em conexão 4G
- **Objetivo 6:** 100% dos dados de saúde criptografados em conformidade com LGPD
- **Objetivo 7:** Uptime da plataforma ≥ 99,5% em produção

---

## 3. Escopo do MVP

### Incluso
- Autenticação segura (admin + cliente) com controle de perfis
- Conformidade LGPD completa (consentimento, criptografia, exclusão de dados)
- Cadastro de clientes com anamnese esportiva detalhada
- Agente IA Coach — ciclismo, musculação, corrida, natação e triathlon
- Orientação nutricional diária integrada ao treino
- Integração bidirecional: Strava, Garmin Connect, TrainingPeaks, Apple Health
- Automação diária: importar → recalcular carga → gerar treino → enviar plataformas
- Cálculo de CTL / ATL / TSB por cliente
- Dashboard admin multi-cliente com alertas
- App mobile (PWA) para cliente visualizar treino do dia
- Feedback opcional pós-treino pelo cliente
- Relatórios semanais/mensais exportáveis em PDF
- Sistema de assinaturas com Stripe

### Excluído (e por quê)
- **App nativo iOS/Android (React Native)** — PWA atende o MVP; nativo exige esforço adicional significativo
- **Suporte a outros países e idiomas** — público-alvo inicial é Brasil; internacionalização é Fase 2
- **Apple Watch nativo** — Apple Health cobre o MVP; integração nativa com watchOS é Fase 2
- **Marketplace de planos de treino** — requer multi-tenant avançado; fora do escopo inicial
- **Telemedicina dentro do app** — fora do escopo; app é de coaching, não de consulta médica

---

## 4. User Stories por Épico

---

### EP-01: Infraestrutura e Setup

**US-001** | Must | M | time de desenvolvimento
> Como desenvolvedor, quero um repositório estruturado com backend e frontend separados para organizar o desenvolvimento.
- [ ] Dado o repositório criado, quando clonar, então existem pastas /backend e /frontend com README de setup
- [ ] Dado o ambiente de desenvolvimento, quando rodar os comandos de setup, então o projeto sobe localmente sem erros
Depende de: —

**US-002** | Must | M | time de desenvolvimento
> Como desenvolvedor, quero banco de dados Supabase configurado com schema inicial para armazenar dados do produto.
- [ ] Dado o Supabase configurado, quando aplicar as migrations, então todas as tabelas são criadas sem erro
- [ ] Dado o banco criado, quando testar a conexão do backend, então retorna sucesso em < 200ms
Depende de: US-001

**US-003** | Should | M | time de desenvolvimento
> Como desenvolvedor, quero deploy automático (backend no Railway, frontend na Vercel) para publicar atualizações com agilidade.
- [ ] Dado push na branch main, quando o CI/CD executar, então backend e frontend são deployados automaticamente
- [ ] Dado o deploy concluído, quando acessar a URL de produção, então o app responde com status 200
Depende de: US-001, US-002

---

### EP-02: Autenticação e LGPD

**US-004** | Must | S | Dr. Admin
> Como admin, quero fazer login seguro com email e senha para acessar o painel de gestão.
- [ ] Dado credenciais válidas, quando fazer login, então sou redirecionado ao dashboard admin em < 1s
- [ ] Dado credenciais inválidas, quando fazer login, então vejo mensagem de erro genérica sem expor detalhes de segurança
- [ ] Dado sessão expirada (> 24h), quando tentar acessar rota protegida, então sou redirecionado ao login
Depende de: US-002

**US-005** | Must | S | Cliente Atleta
> Como cliente, quero fazer login no app com email e senha para visualizar meus treinos.
- [ ] Dado credenciais válidas, quando fazer login, então vejo meu plano de treino do dia
- [ ] Dado perfil de cliente, quando tentar acessar rotas de admin (/admin/*), então recebo erro 403
- [ ] Dado primeiro acesso após convite, quando definir senha, então login é realizado com sucesso
Depende de: US-004

**US-006** | Must | S | Cliente Atleta
> Como cliente, quero aceitar os termos de uso e política de privacidade (LGPD) para autorizar o uso dos meus dados de saúde.
- [ ] Dado primeiro acesso, quando criar conta, então sou obrigado a aceitar termos LGPD antes de prosseguir
- [ ] Dado aceite registrado, quando solicitar exportação dos meus dados, então recebo arquivo completo em < 72h
- [ ] Dado dados de saúde armazenados, quando verificar o banco, então estão criptografados com AES-256 em repouso
Depende de: US-005

**US-007** | Must | S | Dr. Admin
> Como admin, quero gerenciar o consentimento LGPD dos clientes para garantir conformidade legal.
- [ ] Dado painel admin, quando visualizar um cliente, então vejo status do consentimento LGPD e data de aceite
- [ ] Dado solicitação de exclusão de dados, quando o cliente pedir, então executo exclusão completa em ≤ 72h
- [ ] Dado log de acessos, quando auditado, então há registro de quem acessou quais dados e quando (retenção: 1 ano)
Depende de: US-006

---

### EP-03: Gestão de Clientes

**US-008** | Must | M | Dr. Admin
> Como admin, quero cadastrar um novo cliente com dados pessoais e esportivos para o agente IA criar um plano personalizado.
- [ ] Dado formulário de cadastro, quando preencher campos obrigatórios (nome, email, nascimento, peso, altura, objetivo), então cliente é criado com sucesso
- [ ] Dado cliente criado, quando verificar, então ele recebe email de boas-vindas com link de acesso em < 5 minutos
- [ ] Dado campo obrigatório vazio, quando tentar salvar, então vejo erro de validação específico por campo
Depende de: US-004

**US-009** | Must | M | Dr. Admin
> Como admin, quero registrar a anamnese esportiva do cliente para que a IA crie planos seguros e eficazes.
- [ ] Dado perfil do cliente, quando preencher anamnese, então salvo: histórico de lesões, medicamentos, nível de condicionamento (iniciante/intermediário/avançado), FTP estimado (W), FC máxima, FC de repouso
- [ ] Dado anamnese salva, quando IA gerar plano, então ela utiliza esses dados como parâmetros obrigatórios
- [ ] Dado dados médicos sensíveis, quando armazenados, então estão criptografados com AES-256 conforme LGPD
Depende de: US-008

**US-010** | Must | S | Dr. Admin
> Como admin, quero definir disponibilidade semanal e objetivos do cliente para que a IA respeite a agenda real da pessoa.
- [ ] Dado perfil do cliente, quando configurar disponibilidade, então marco dias e horários por modalidade (ciclismo, musculação, corrida, natação)
- [ ] Dado objetivo definido (ex: perda de peso, performance, preparação para prova), quando IA gerar plano, então objetivo é refletido na periodização
- [ ] Dado atualização de disponibilidade, quando salvar, então o próximo plano gerado já considera a nova agenda
Depende de: US-009

**US-011** | Must | M | Dr. Admin
> Como admin, quero listar e filtrar todos os clientes com indicadores de status para gerenciar a carteira de alunos.
- [ ] Dado lista de clientes, quando acessar o painel, então vejo: nome, último treino, TSB atual (colorido: verde/amarelo/vermelho), status de integração
- [ ] Dado busca por nome ou email, quando filtrar, então resultado aparece em < 500ms
- [ ] Dado cliente sem treino registrado há ≥ 3 dias, quando visualizar lista, então aparece com badge de alerta laranja
Depende de: US-008

**US-012** | Must | L | Cliente Atleta
> Como cliente, quero conectar minha conta do Strava, Garmin, TrainingPeaks ou Apple Health para que o agente envie e receba meus treinos automaticamente.
- [ ] Dado meu perfil, quando clicar em "Conectar [plataforma]", então sou redirecionado ao OAuth da plataforma
- [ ] Dado autorização concluída, quando voltar ao app, então vejo status "Conectado ✓" com ícone da plataforma
- [ ] Dado conexão ativa, quando a IA gerar um treino, então ele é enviado automaticamente à plataforma escolhida
Depende de: US-005

---

### EP-04: Agente IA Coach

**US-013** | Must | XL | Agente IA Coach
> Como sistema, quero um agente IA com conhecimento profundo em medicina do esporte para gerar planos tecnicamente precisos.
- [ ] Dado perfil completo do cliente, quando solicitar geração de plano, então agente retorna plano estruturado em JSON com sessões detalhadas em < 30s
- [ ] Dado plano gerado, quando verificar, então inclui: tipo de treino, duração, intensidade por zonas, descrição de cada bloco
- [ ] Dado nível do cliente, quando gerar plano, então progressão de carga respeita princípios de periodização (progressão gradual, semanas de recuperação a cada 3-4 semanas)
Depende de: US-009, US-010

**US-014** | Must | L | Agente IA Coach
> Como sistema, quero que o agente analise o TSB do cliente antes de gerar o treino do dia para evitar overtraining.
- [ ] Dado TSB < -20, quando gerar treino do dia, então agente prescreve recuperação ativa ou treino muito leve (RPE ≤ 5)
- [ ] Dado TSB entre -5 e +5, quando gerar treino, então intensidade moderada-alta é prescrita (zonas 3-4)
- [ ] Dado TSB > +10, quando gerar treino, então sessão de qualidade (threshold/VO2max) é recomendada
- [ ] Dado decisão do agente, quando verificar log, então há justificativa explícita baseada nos dados de carga
Depende de: US-013, US-022

**US-015** | Must | L | Agente IA Coach
> Como sistema, quero que o agente gere planos para ciclismo, musculação, corrida, natação e triathlon com estrutura específica por modalidade.
- [ ] Dado treino de ciclismo, quando gerado, então inclui: aquecimento, blocos com targets em watts/% FTP/zona FC, desaquecimento
- [ ] Dado treino de musculação, quando gerado, então inclui: exercícios com séries, reps, carga (% 1RM ou RPE alvo) e tempo de descanso
- [ ] Dado treino de corrida, quando gerado, então inclui: ritmo alvo (min/km), zonas de FC, tipo de sessão (longa/intervalado/regenerativo)
- [ ] Dado treino de natação, quando gerado, então inclui: distâncias por estilo, tempos alvo e pausas
- [ ] Dado treino de triathlon, quando gerado, então combina as 3 modalidades com blocos de transição
Depende de: US-013

**US-016** | Must | L | Agente IA Coach
> Como sistema, quero que o agente ajuste o plano após receber os dados do treino executado para adaptar a prescrição seguinte.
- [ ] Dado dados pós-treino recebidos, quando analisar, então agente compara realizado vs planejado (distância, potência, FC, TSS)
- [ ] Dado desvio > 20% da carga planejada, quando detectado, então próximo treino é reajustado proporcionalmente
- [ ] Dado feedback subjetivo do cliente, quando fornecido, então agente incorpora na adaptação (ex: RPE reportado > planejado → reduz intensidade)
- [ ] Dado ajuste realizado, quando verificar log, então há registro do motivo da alteração com dados comparativos
Depende de: US-013, US-023

**US-017** | Should | S | Dr. Admin
> Como admin, quero visualizar o raciocínio do agente IA ao gerar cada treino para entender e validar as decisões.
- [ ] Dado plano gerado, quando verificar detalhes no painel, então vejo rationale: métricas consideradas (CTL/ATL/TSB), motivo da intensidade escolhida, dados do último treino
- [ ] Dado histórico de planos, quando acessar plano anterior, então o raciocínio do agente está preservado com timestamp
Depende de: US-013

---

### EP-05: Integrações Externas

**US-018** | Must | L | Agente IA Coach
> Como sistema, quero enviar o treino planejado para o Strava do cliente.
- [ ] Dado treino gerado, quando enviar ao Strava via API v3, então aparece como "Treino Planejado" na conta do cliente
- [ ] Dado falha no envio, quando ocorrer, então sistema tenta novamente 3x com backoff exponencial e notifica o admin se persistir
Depende de: US-012, US-015

**US-019** | Must | L | Agente IA Coach
> Como sistema, quero enviar o treino planejado para o Garmin Connect como workout estruturado.
- [ ] Dado treino gerado, quando enviar ao Garmin, então aparece no Garmin Connect como workout estruturado com intervalos
- [ ] Dado workout enviado, quando o cliente sincronizar o relógio Garmin, então treino aparece no dispositivo
- [ ] Dado falha, quando ocorrer, então retry automático 3x e alerta ao admin
Depende de: US-012, US-015

**US-020** | Must | L | Agente IA Coach
> Como sistema, quero enviar o treino planejado para o TrainingPeaks.
- [ ] Dado treino gerado, quando enviar ao TrainingPeaks via API, então aparece no calendário como workout planejado com estrutura de intervalos correta (targets, durações, descrições)
- [ ] Dado falha, quando ocorrer, então retry 3x e alerta ao admin
Depende de: US-012, US-015

**US-021** | Must | XL | Agente IA Coach
> Como sistema, quero receber automaticamente os dados do treino executado das plataformas para alimentar o agente IA.
- [ ] Dado treino concluído no Strava/Garmin/TrainingPeaks, quando sincronizado, então dados chegam ao sistema em ≤ 30 minutos via webhook ou polling
- [ ] Dado dados recebidos, quando processados, então incluem: duração real, distância, potência média/normalizada, FC média/máxima, TSS calculado
- [ ] Dado dados importados, quando verificar banco, então treino está vinculado ao cliente correto e à prescrição original
Depende de: US-018, US-019, US-020

**US-021b** | Must | L | Agente IA Coach
> Como sistema, quero receber dados do Apple Health do cliente (FC, calorias, sono, atividades) para complementar a análise do agente IA.
- [ ] Dado cliente com Apple Health conectado, quando sincronizar, então dados de FC de repouso, horas de sono e atividades chegam ao sistema diariamente
- [ ] Dado dados do Apple Health, quando processados, então agente os considera na análise de recuperação e ajuste de carga
- [ ] Dado armazenamento de dados Apple Health, quando verificar, então conformidade LGPD é mantida (criptografia + consentimento registrado)
Depende de: US-012

---

### EP-06: Planos e Treinos

**US-022** | Must | M | Agente IA Coach
> Como sistema, quero calcular CTL, ATL e TSB diariamente para cada cliente para mensurar carga de treino.
- [ ] Dado histórico de treinos do cliente, quando calcular, então CTL usa média exponencial de 42 dias e ATL usa 7 dias (modelo Banister PMC)
- [ ] Dado novo treino importado, quando processar, então CTL/ATL/TSB são recalculados automaticamente
- [ ] Dado cálculo realizado, quando verificar banco, então há registro de CTL/ATL/TSB para cada data desde o início do acompanhamento
Depende de: US-021

**US-023** | Must | M | Cliente Atleta
> Como cliente, quero visualizar meu treino do dia no app para saber o que fazer hoje.
- [ ] Dado app mobile, quando abrir, então vejo o treino de hoje em destaque com tipo, duração e intensidade geral
- [ ] Dado treino de ciclismo, quando visualizar, então vejo blocos com watts alvo, zona FC e duração de cada intervalo
- [ ] Dado treino de musculação, quando visualizar, então vejo lista de exercícios com séries, reps e carga
- [ ] Dado dia de descanso prescrito, quando visualizar, então vejo orientações de recuperação ativa
Depende de: US-015

**US-024** | Should | M | Cliente Atleta
> Como cliente, quero visualizar meu histórico de treinos e evolução para acompanhar meu progresso.
- [ ] Dado histórico, quando acessar, então vejo lista dos últimos 30 treinos com data, tipo, TSS e status (realizado/planejado/perdido)
- [ ] Dado gráfico de evolução, quando visualizar, então vejo CTL/ATL/TSB dos últimos 60 dias em linha temporal
- [ ] Dado treino específico, quando tocar, então vejo detalhes completos: planejado vs executado com diferenças destacadas
Depende de: US-023, US-022

**US-025** | Must | M | Dr. Admin
> Como admin, quero visualizar o plano e histórico de treinos de qualquer cliente para acompanhar a evolução da carteira.
- [ ] Dado perfil do cliente no painel admin, quando acessar, então vejo o mesmo histórico e gráficos visíveis ao cliente
- [ ] Dado comparativo planejado vs executado, quando analisar, então vejo aderência ao plano em % (meta: ≥ 80%)
- [ ] Dado alerta de carga elevada (TSB < -25), quando detectado, então admin é notificado via badge no painel
Depende de: US-024

---

### EP-07: Automação Diária

**US-026** | Must | L | Agente IA Coach
> Como sistema, quero executar um job diário automático para cada cliente ativo sem necessidade de ação manual.
- [ ] Dado job agendado às 6h diariamente, quando executar, então para cada cliente ativo em paralelo: importa treinos das últimas 24h, recalcula CTL/ATL/TSB, gera treino do dia seguinte com nutrição, envia às plataformas conectadas
- [ ] Dado job concluído, quando verificar log, então há registro de sucesso/falha por cliente com timestamp e duração de execução
- [ ] Dado falha no processamento de um cliente, quando ocorrer, então erro é registrado sem interromper processamento dos demais
Depende de: US-016, US-021, US-022

**US-027** | Should | S | Dr. Admin
> Como admin, quero visualizar o log de execução do job diário para monitorar a saúde do sistema.
- [ ] Dado painel admin, quando acessar logs, então vejo execuções dos últimos 7 dias com status (✓/✗) por cliente
- [ ] Dado erro de integração persistente (> 3 falhas consecutivas), quando detectado, então aparece alerta crítico no dashboard
- [ ] Dado job não executado no horário esperado (tolerância: 30min), quando verificar, então há alerta de falha crítica
Depende de: US-026

---

### EP-08: Dashboard Admin

**US-028** | Must | M | Dr. Admin
> Como admin, quero um dashboard com visão consolidada de todos os clientes para gerenciar minha carteira eficientemente.
- [ ] Dado dashboard, quando acessar, então vejo cards por cliente com: nome, treino de hoje, TSB atual (colorido), status de integração, data do último treino
- [ ] Dado dashboard com ≥ 10 clientes, quando carregar, então página renderiza completamente em < 2 segundos
- [ ] Dado uso no celular, quando acessar, então layout é responsivo e todos os cards são legíveis em tela de 360px
Depende de: US-011, US-025

**US-029** | Should | M | Dr. Admin
> Como admin, quero receber alertas automáticos de situações críticas dos clientes para agir rapidamente.
- [ ] Dado TSB de cliente < -25 (risco de overtraining), quando detectado às 6h, então admin recebe notificação no app
- [ ] Dado falha de integração por ≥ 24h sem resolução, quando detectada, então admin é alertado com descrição técnica
- [ ] Dado cliente sem treino registrado há ≥ 5 dias, quando detectado, então admin recebe aviso de engajamento
Depende de: US-028

---

### EP-09: App Mobile Cliente

**US-030** | Must | L | Cliente Atleta
> Como cliente, quero um app mobile responsivo (PWA) para acessar meus treinos de qualquer dispositivo.
- [ ] Dado acesso via smartphone, quando abrir o app, então layout se adapta perfeitamente a telas ≥ 360px de largura
- [ ] Dado app instalado como PWA, quando acessar sem internet, então treino do dia carregado previamente está disponível offline
- [ ] Dado carregamento, quando acessar o treino do dia em 4G, então página renderiza em < 2 segundos
Depende de: US-023

**US-031** | Should | S | Cliente Atleta
> Como cliente, quero fornecer feedback opcional após o treino para ajudar o agente IA a melhorar as prescrições.
- [ ] Dado treino do dia, quando concluir e abrir o app, então vejo opção de feedback: "Como foi? (1-10)" + campo de texto livre
- [ ] Dado feedback enviado, quando processado pelo agente, então é considerado na geração do próximo treino como ajuste de intensidade
- [ ] Dado feedback não enviado, quando não interagir, então sistema funciona normalmente sem degradação
Depende de: US-023

---

### EP-10: Sistema de Assinaturas

**US-032** | Must | M | Dr. Admin
> Como admin, quero gerenciar assinaturas dos clientes (ativar, suspender, cancelar) para controlar o acesso à plataforma.
- [ ] Dado painel admin, quando gerenciar assinaturas, então consigo ativar, suspender ou cancelar acesso de cada cliente com 1 clique
- [ ] Dado assinatura suspensa, quando cliente tentar acessar, então vê tela de "Conta inativa" com instruções para contato
- [ ] Dado histórico de assinaturas, quando verificar, então vejo datas de início, suspensão e cancelamento com motivo
Depende de: US-008

**US-033** | Should | L | Dr. Admin
> Como admin, quero integração com Stripe para automatizar cobranças das assinaturas.
- [ ] Dado cliente com assinatura ativa, quando chegar data de renovação, então cobrança recorrente é processada automaticamente via Stripe
- [ ] Dado cobrança recusada, quando ocorrer, então admin e cliente são notificados por email e acesso é suspenso após 3 dias de carência
- [ ] Dado painel financeiro, quando acessar, então vejo: receita mensal recorrente (MRR), clientes ativos, inadimplentes e histórico de transações
Depende de: US-032

---

### EP-11: Orientação Nutricional

**US-034** | Must | L | Agente IA Coach
> Como sistema, quero gerar orientações nutricionais diárias baseadas no treino do dia para otimizar performance e recuperação do cliente.
- [ ] Dado treino de alta intensidade (TSS > 80) gerado, quando criar orientação nutricional, então inclui: estimativa de carboidratos (g/kg), proteínas (g/kg), hidratação (ml), timing de refeições pré e pós-treino
- [ ] Dado dia de descanso prescrito, quando criar orientação, então foca em recuperação: proteína (1,6-2,0g/kg), anti-inflamatórios naturais, hidratação basal
- [ ] Dado perfil do cliente (peso, objetivo), quando gerar orientação, então valores são personalizados ao peso e meta do atleta
Depende de: US-015

**US-035** | Must | S | Cliente Atleta
> Como cliente, quero visualizar minhas orientações nutricionais do dia junto ao treino para facilitar minha rotina.
- [ ] Dado app mobile, quando visualizar treino do dia, então seção "Nutrição do Dia" aparece abaixo do treino com recomendações práticas
- [ ] Dado orientação nutricional, quando visualizar, então linguagem é simples e prática, sem jargão técnico excessivo
Depende de: US-034, US-023

---

### EP-12: Relatórios de Atividades

**US-036** | Must | M | Dr. Admin
> Como admin, quero gerar relatório semanal/mensal de cada cliente para acompanhar minha carteira.
- [ ] Dado relatório semanal, quando gerar, então inclui: treinos realizados vs planejados (%), TSS total da semana, evolução CTL/ATL/TSB, principais insights da IA
- [ ] Dado relatório, quando exportar, então gera PDF bem formatado e legível em < 10 segundos
- [ ] Dado seleção de cliente e período no painel admin, quando confirmar, então relatório é gerado corretamente
Depende de: US-025

**US-037** | Should | S | Dr. Admin
> Como admin, quero enviar o relatório ao cliente por email para manter engajamento e transparência.
- [ ] Dado relatório gerado, quando clicar em "Enviar ao cliente", então cliente recebe email com PDF anexado em < 5 minutos
- [ ] Dado envio automático semanal ativado, quando chegar domingo às 20h, então relatório da semana é enviado automaticamente a todos os clientes com envio ativo
Depende de: US-036

**US-038** | Should | M | Cliente Atleta
> Como cliente, quero acessar meu relatório mensal no app para acompanhar minha evolução de forma visual.
- [ ] Dado app mobile, quando acessar seção "Relatórios", então vejo resumo visual do mês com gráficos de evolução de carga e aderência
- [ ] Dado relatório, quando tocar em "Exportar", então consigo salvar ou compartilhar o PDF
Depende de: US-036

---

## 5. Requisitos Não-Funcionais

| ID | Categoria | Requisito |
|----|-----------|-----------|
| NFR-01 | Performance | APIs do backend respondem em < 500ms no percentil 95 |
| NFR-02 | Performance | Geração de plano pela IA concluída em < 30 segundos por cliente |
| NFR-03 | Performance | Job diário processa todos os clientes ativos em < 10 minutos no total |
| NFR-04 | Performance | Dados pós-treino importados das plataformas em ≤ 30 minutos após sincronização |
| NFR-05 | Performance | App mobile carrega treino do dia em < 2 segundos em 4G |
| NFR-06 | Segurança | Autenticação via JWT com refresh token (expiração: 24h access / 30d refresh) |
| NFR-07 | Segurança | Senhas armazenadas com bcrypt (cost factor ≥ 12) |
| NFR-08 | Segurança | Dados de saúde criptografados em repouso com AES-256 |
| NFR-09 | Segurança | Comunicação exclusivamente via HTTPS/TLS 1.3 |
| NFR-10 | Segurança | Tokens OAuth de plataformas externas armazenados criptografados, nunca em logs |
| NFR-11 | LGPD | Consentimento registrado com timestamp e versão dos termos aceitos |
| NFR-12 | LGPD | Dados pessoais exportáveis e deletáveis por solicitação em ≤ 72h |
| NFR-13 | LGPD | Log de auditoria de acessos a dados de saúde retido por 1 ano |
| NFR-14 | Disponibilidade | Uptime ≥ 99,5% em produção (tolerância: ~3,6h/mês de downtime) |
| NFR-15 | Escalabilidade | Suportar até 50 clientes simultâneos no MVP sem degradação de performance |
| NFR-16 | Manutenibilidade | Cobertura de testes automatizados ≥ 70% nas funções críticas (cálculo de carga, geração de treino) |

---

## 6. Restrições e Premissas

### Restrições
- **Equipe:** 1 desenvolvedor + IA (Claude Code) — escopo deve ser factível para esse contexto
- **APIs externas:** Strava, Garmin e TrainingPeaks têm limites de requisições (rate limiting) — job diário deve respeitar esses limites
- **Garmin API:** acesso à API oficial requer aprovação; pode usar Strava como relay inicial caso não aprovado
- **Apple Health:** integração via HealthKit requer que o cliente use iOS; usuários Android terão apenas Strava/Garmin/TrainingPeaks
- **LGPD:** dados de saúde são dados sensíveis (Art. 11 LGPD) — requerem consentimento expresso e proteção reforçada
- **Stripe:** disponível para PJ no Brasil; admin precisa ter conta Stripe configurada antes do go-live

### Premissas
- O admin (Dr.) possui conta Supabase, Railway/Render e Vercel configuradas
- Clientes possuem conta em pelo menos uma das plataformas suportadas (Strava, Garmin ou TrainingPeaks)
- O agente IA usará Claude API (Anthropic) como provider principal
- PWA é suficiente para o MVP; app nativo não é necessário inicialmente
- Idioma único: português brasileiro

---

## 7. Roadmap Pós-MVP

### Fase 2 — Expansão de Plataformas
- Integração nativa com Apple Watch (watchOS)
- Integração com Polar Flow
- App nativo iOS e Android (React Native)

### Fase 3 — Expansão de Funcionalidades
- Suporte a múltiplos países e idiomas (inglês, espanhol)
- Planos de nutrição detalhados com diário alimentar
- Análise de composição corporal (integração com balança smart)
- Telemedicina integrada (consulta médica esportiva)

### Fase 4 — Escala de Negócio
- Marketplace de planos de treino (coaches terceiros)
- White-label para academias e clubes de ciclismo
- API pública para integrações de terceiros
- Multi-tenancy completo (múltiplos admins/coaches)

---

## 8. Glossário

| Termo | Definição |
|-------|-----------|
| **CTL** | Chronic Training Load — carga crônica de treino, média exponencial de 42 dias do TSS diário. Representa o "fitness" do atleta |
| **ATL** | Acute Training Load — carga aguda de treino, média exponencial de 7 dias do TSS diário. Representa a "fadiga" recente |
| **TSB** | Training Stress Balance — equilíbrio entre fitness e fadiga: TSB = CTL - ATL. Positivo = forma boa; muito negativo = overtraining |
| **TSS** | Training Stress Score — pontuação de estresse de uma sessão de treino. Calculado com base em duração, potência normalizada e FTP |
| **FTP** | Functional Threshold Power — potência sustentável por ~60 minutos. Referência para calcular zonas de potência no ciclismo |
| **NP** | Normalized Power — potência normalizada que considera variações de intensidade ao longo do treino |
| **IF** | Intensity Factor — razão entre NP e FTP. IF = NP/FTP |
| **RPE** | Rate of Perceived Exertion — escala subjetiva de esforço percebido (1-10 ou 6-20 de Borg) |
| **HRV** | Heart Rate Variability — variabilidade da frequência cardíaca; indicador de recuperação do sistema nervoso autônomo |
| **PWA** | Progressive Web App — aplicação web com funcionalidades de app nativo (instalação, offline, notificações push) |
| **OAuth 2.0** | Protocolo de autorização usado pelas plataformas externas (Strava, Garmin, TrainingPeaks) |
| **Webhook** | Notificação automática enviada por uma plataforma ao nosso sistema quando um evento ocorre (ex: treino concluído) |
| **Periodização** | Organização sistemática do treino em ciclos de carga e recuperação para maximizar adaptação e minimizar lesões |
| **PMC** | Performance Management Chart — gráfico de gestão de performance que plota CTL, ATL e TSB ao longo do tempo |
