# Kasiski — Public Market Intelligence

Kasiski é uma plataforma de inteligência para o mercado público que transforma grandes volumes de
informação em oportunidades aderentes ao perfil de cada empresa. Este repositório é o app de licitações
(Lei 14.133/2021): monitora editais no PNCP, confere a habilitação da empresa contra o edital, analisa
concorrentes, gera minutas de peças (impugnação, recurso etc.) e acompanha prazos e contratos — tudo com
IA e verificação cruzada entre modelos.

**Status:** MVP funcional, testado de ponta a ponta em modo demonstração (sem chaves de IA). As
integrações com PNCP, Receita Federal, TCU e Portal da Transparência foram escritas com base na
documentação oficial de cada uma, mas **nunca fizeram uma chamada real** — o ambiente onde isso foi
construído não tinha saída de rede para essas APIs. É bem provável que o primeiro teste com internet de
verdade exija pequenos ajustes de formato de campo. Veja "Limitações conhecidas" no fim deste arquivo.

## Estrutura

```
certame/
├── README.md
├── render.yaml            # blueprint do Render — precisa ficar na RAIZ do repositório
├── backend/               # API Flask
│   ├── app.py             # ponto de entrada
│   ├── config.py          # variáveis de ambiente
│   ├── models.py          # tabelas (SQLAlchemy)
│   ├── auth.py            # login por token JWT
│   ├── planos.py          # planos, limites de uso
│   ├── routes/             # uma rota por área (editais, empresas, peças...)
│   ├── services/           # IA, PNCP, Receita/TCU/CGU, prazos, base de conhecimento
│   ├── jobs/               # tarefa agendada do radar (roda 1x/dia)
│   ├── knowledge-base/      # .md usados como contexto legal para a IA
│   ├── requirements.txt
│   └── .env.example
└── frontend/              # HTML/CSS/JS puro (sem build, sem framework)
    ├── index.html
    ├── css/app.css
    └── js/
        ├── config.js        # AJUSTAR antes de publicar (URL do backend)
        ├── nucleo.js         # estado, API, componentes
        ├── app.js            # roteador
        └── views/            # uma tela por arquivo
```

## Rodando localmente

Precisa de Python 3.11+ e de conseguir servir arquivos estáticos (qualquer servidor HTTP simples).

**Backend:**
```bash
cd certame/backend
python -m venv .venv && source .venv/bin/activate   # opcional, mas recomendado
pip install -r requirements.txt
cp .env.example .env
# edite o .env: pelo menos ADMIN_EMAILS com o seu e-mail
python app.py
```
Sobe em `http://localhost:5000`. Sem nenhuma chave de IA configurada, o app roda em **modo
demonstração** — todas as telas funcionam, mas as respostas de IA são exemplos fixos, não análises
reais. Isso é o esperado até você colocar suas chaves.

**Frontend:**
```bash
cd certame/frontend
python -m http.server 8080
```
Abra `http://localhost:8080`. O `js/config.js` já aponta para `http://localhost:5000` quando o
`location.hostname` é `localhost`, então local-a-local funciona sem editar nada.

**Página inicial pública:** visitantes sem login caem em `#/` — apresentação, recursos, setores, planos
(lidos de `GET /api/planos`, a mesma tabela que controla os limites no backend) e dúvidas frequentes. O
texto fica em `frontend/js/views/inicio.js`. Quem já está logado vai direto para o Painel.

**Primeiro acesso:** vá em "Criar conta grátis", cadastre-se com o e-mail que você colocou em
`ADMIN_EMAILS` no `.env` — esse usuário ganha acesso à tela **Administração** (gerenciar revisões pagas
e planos das contas).

## Deploy em produção

A infraestrutura foi pensada para ficar barata desde o primeiro cliente: backend no Render (com banco
Postgres do próprio Render), frontend estático no Netlify.

### 1. Backend no Render

O arquivo `render.yaml`, na **raiz do repositório** (não dentro de `backend/`), é um blueprint pronto:
cria o serviço web, o cron do radar e o banco Postgres de uma vez. O Render só encontra esse arquivo
automaticamente se ele estiver na raiz — é por isso que ele fica fora da pasta `backend/`, mesmo
descrevendo um serviço cujo código está lá dentro (a linha `rootDir: backend` de cada serviço é o que
diz ao Render onde entrar para rodar `pip install` e iniciar o app).

1. Suba a pasta `certame` inteira (com `render.yaml` na raiz) para um repositório Git (GitHub, por exemplo).
2. No Render, **New → Blueprint**, aponte para o repositório.
3. O Render vai pedir para preencher as variáveis marcadas `sync: false` no `render.yaml`:
   - `CORS_ORIGINS` → o domínio do seu frontend no Netlify (ex.: `https://certame.netlify.app`)
   - `ADMIN_EMAILS` → seu e-mail
   - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` → veja abaixo onde conseguir
   - `PORTAL_TRANSPARENCIA_KEY` → opcional, veja abaixo
4. Depois do deploy, confira `https://SEU-APP.onrender.com/api/saude` — deve responder
   `{"ok": true, "modo_demonstracao": false}` (false só depois de configurar pelo menos uma chave de IA).

> **Erro "Blueprint file `render.yaml` not found on main branch"**: quase sempre é um destes dois
> problemas. (1) O `render.yaml` não está na raiz do que foi enviado ao Render — confira se, ao navegar
> pelo repositório no GitHub, o arquivo aparece direto na listagem principal, não dentro de `backend/`.
> (2) O branch padrão do seu repositório não se chama `main` (repositórios criados há mais tempo às
> vezes usam `master`, ou você pode ter subido para um branch com outro nome) — confira o nome do branch
> no GitHub e, se for diferente, ou renomeie para `main` ou selecione o branch correto na tela de
> configuração do Blueprint no Render. Se preferir não depender do Blueprint, dá para criar os três
> recursos manualmente: **New → Web Service** (aponte para o repositório, *Root Directory* = `backend`,
> *Build Command* = `pip install -r requirements.txt`, *Start Command* =
> `gunicorn app:app --workers 2 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT`), depois **New →
> PostgreSQL** e **New → Cron Job** (mesmo Root Directory, comando `python jobs/radar_diario.py`,
> agendamento `0 9 * * 1-5`) separadamente, ligando a `DATABASE_URL` do banco criado às variáveis de
> ambiente dos outros dois.

O plano pago do Render (a partir de ~US$ 7/mês) é necessário para o disco persistente (onde ficam os
PDFs enviados) e para o cron job não dormir. O banco Postgres "basic-256mb" cobre bem o início.

### 2. Frontend no Netlify

1. Antes de publicar, edite `frontend/js/config.js`:
   ```js
   API_URL: "https://SEU-APP.onrender.com",
   LINK_ASSINATURA: "https://wa.me/55SEUNUMERO?text=...",  // ou link de checkout
   ```
2. Suba a pasta `certame/frontend` para o Netlify (arrastar a pasta no painel funciona; ou conecte o
   repositório Git e configure o *publish directory* como `frontend`).
3. Nenhum *build command* é necessário — é HTML/JS puro.

### 3. Onde conseguir cada chave

| Chave | Onde | Custo |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | pré-pago, por uso |
| `OPENAI_API_KEY` | platform.openai.com | pré-pago, por uso |
| `GEMINI_API_KEY` | aistudio.google.com/apikey | tem faixa gratuita |
| `PORTAL_TRANSPARENCIA_KEY` | portaldatransparencia.gov.br/api-de-dados (cadastro por e-mail) | gratuita |

Sem `PORTAL_TRANSPARENCIA_KEY`, o dossiê de concorrentes funciona normalmente, só não traz o resultado
de sanções do CEIS/CNEP (mostra "sem chave" em vez de consultar).

O app **não exige todas as chaves de IA** para sair do modo demonstração — basta uma. Mas a regra de
verificação cruzada (Claude analisa, outro fornecedor confere) só funciona de verdade com pelo menos
duas chaves de fornecedores diferentes configuradas; com uma só, a "verificação cruzada" usa o mesmo
fornecedor, o que reduz o valor da checagem.

### Custo mensal estimado

- Render (web + cron + banco): a partir de ~US$ 25–40/mês
- Netlify: gratuito no plano inicial
- IA: variável por uso; para um volume pequeno (dezenas de análises/mês), algumas dezenas de dólares

## Banco de dados e migrações

O app usa SQLite por padrão (`DATABASE_URL=sqlite:///certame.db`) e Postgres em produção (Render injeta
a `DATABASE_URL` automaticamente). Não há Alembic configurado: o próprio `app.py` cria as tabelas que
faltam (`db.create_all()`) e adiciona colunas novas a tabelas já existentes (`_migrar_colunas_novas`,
em `app.py`) toda vez que sobe. Isso cobre bem a fase atual (só adicionar campos), mas **não** cobre
renomear ou remover colunas — se isso for necessário no futuro, vale migrar para Alembic.

## Base de conhecimento (RAG)

`backend/knowledge-base/*.md` — 16 arquivos, cobrindo as regras gerais da Lei 14.133 (competitividade,
prazos, habilitação, propostas/exequibilidade, ME/EPP, execução contratual, sanções, dispensa e
inexigibilidade) e 6 segmentos setoriais (obras/engenharia, registro de preços/fornecimento, saúde,
educação, TI, segurança/vigilância, transporte, alimentação).

A busca é por sobreposição de palavras-chave (`backend/services/kb.py`), não por embeddings — decisão
deliberada para manter custo zero nesta fase. Funciona bem porque as consultas são sempre montadas com
termos jurídicos específicos contra um corpus pequeno e também jurídico. Para ampliar: basta criar mais
arquivos `.md` na pasta, com seções iniciadas por `## ` — não precisa mexer em código. Se um dia a base
crescer muito (centenas de arquivos) e a precisão por palavra-chave não for mais suficiente, troque a
implementação de `buscar()` em `kb.py` por embeddings + pgvector; a função é chamada sempre da mesma
forma em `fluxos.py`, então essa troca não exige mudar quem a usa.

## Limitações conhecidas

- **APIs externas nunca testadas ao vivo**: `services/pncp.py` e `services/dados_publicos.py` (PNCP,
  BrasilAPI/Receita, TCU, Portal da Transparência, Compras.gov.br) foram escritos com base na
  documentação oficial e revisados, mas nunca fizeram uma chamada real durante o desenvolvimento. Teste
  cedo, em ambiente com internet, e ajuste nomes de campo se necessário.
- **RAG por palavra-chave, não semântico**: veja a seção acima. Funciona bem para este caso de uso, mas
  não generaliza para sinônimos distantes.
- **Sem Alembic**: migrações de schema mais complexas (renomear/remover coluna) exigem intervenção
  manual.
- **Job do radar nunca executado de verdade**: `backend/jobs/radar_diario.py` foi revisado mas não
  rodou em produção. Teste manualmente (`python jobs/radar_diario.py`) antes de confiar no cron.

## Contas de teste usadas durante o desenvolvimento

Nenhuma — o banco de dados não está incluído neste pacote. O primeiro cadastro que você fizer já começa
limpo.


## Cobrança (Mercado Pago), CRM, funil e receitas

### Como funciona
- **Planos pagos**: Essencial (R$ 197), Profissional (R$ 497), Avançado (R$ 799, inclui a proposta comercial com IA) e Consultor (R$ 1.290), com ciclo **mensal** ou **anual** (anual = preço mensal × `ANUAL_MESES_PAGOS`, padrão 10 → "2 meses grátis").
- **Duas formas de pagar** (tela *Plano e conta*):
  - **Cartão com renovação automática**: Assinaturas do Mercado Pago (`/preapproval`). Cobra sozinho todo ciclo.
  - **Pix, boleto ou cartão avulso**: Checkout Pro. Vale 1 ciclo; o cliente renova pagando de novo (aparece um aviso 5 dias antes do vencimento).
- Cada pagamento aprovado estende `pago_ate` da conta por 1 ou 12 meses. Vencido há mais de `CARENCIA_DIAS`, a conta passa para *suspenso* (os dados ficam salvos). Contas com plano definido manualmente pelo administrador, sem data de vencimento, nunca são suspensas automaticamente.
- **Administração** (menu *Administração*, só para `ADMIN_EMAILS`):
  - **Clientes e testes**: CRM de todas as contas: etapa, plano, fim do teste, uso da IA, receita, custo de IA, último acesso, anotações, etiquetas e “+7 dias de teste”.
  - **Funil de conversão**: visita → clique em testar → cadastro → empresa cadastrada → 1ª análise → abriu pagamento → assinante; por origem (`utm_source`) e lista de leads quentes.
  - **Receitas**: MRR, ARR, recebido por mês (assinaturas × serviços), tarifas do Mercado Pago, custo de IA em R$, resultado, cancelamentos e lançamentos manuais.

### Configuração (uma vez)
1. No Mercado Pago: **Suas integrações → Criar aplicação** (produto: Checkout Pro + Assinaturas). Copie o **Access Token de produção** (`APP_USR-...`). Para testar, use as credenciais de teste e usuários de teste.
2. Em **Webhooks** da aplicação, cadastre a URL `https://SEU-BACKEND.onrender.com/api/billing/webhook` com os eventos **Pagamentos**, **Planos e assinaturas** (`subscription_preapproval`) e **Pagamentos recorrentes** (`subscription_authorized_payment`). Copie a **assinatura secreta**.
3. No Render (serviço da API), em Environment:
   - `MP_ACCESS_TOKEN` = access token
   - `MP_WEBHOOK_SECRET` = assinatura secreta do webhook
   - `BACKEND_URL` = `https://SEU-BACKEND.onrender.com` (sem barra no final)
   - `FRONTEND_URL` = `https://kasiski.netlify.app`
   - `CORS_ORIGINS` = `https://kasiski.netlify.app` (a barra final agora é ignorada)
   - Opcionais: `ANUAL_MESES_PAGOS` (10), `CARENCIA_DIAS` (3), `USD_BRL` (5.5)
4. Sem `MP_ACCESS_TOKEN`, o botão *Assinar* continua abrindo o `LINK_ASSINATURA` do `config.js` (WhatsApp).

As tabelas e colunas novas (`cobranca`, `evento` e campos em `conta`/`usuario`) são criadas sozinhas ao subir o backend.


## Verificação de e-mail no cadastro e proteção do login

- Cadastro novo recebe um **código de 6 números** por e-mail (vale 15 min, 5 tentativas, reenvio a cada 60 s e no máximo 5 por hora). Sem confirmar, a conta não acessa o sistema; ao tentar entrar depois, um novo código é enviado.
- Contas criadas antes desta versão continuam entrando normalmente.
- **5 senhas erradas seguidas** pausam o login daquele e-mail por 15 minutos.
- No CRM do admin, contas sem e-mail confirmado aparecem com a etiqueta "e-mail não confirmado".

### Configurar o Resend (uma vez)
1. Crie a conta em resend.com → **Domains → Add domain** (ex.: `kasiski.com.br`) e cadastre no DNS do domínio os registros que ele mostrar (SPF/DKIM). Aguarde o status *Verified*.
2. **API Keys → Create** (permissão *Sending access*).
3. No Render: `RESEND_API_KEY` = a chave; `EMAIL_REMETENTE` = `Kasiski <nao-responda@SEU-DOMINIO>` (precisa ser do domínio verificado).
4. `VERIFICAR_EMAIL`: `auto` (padrão: exige o código só quando `RESEND_API_KEY` está preenchida), `sim` ou `nao`.


## Preços e propostas (inteligência de preços + minuta de proposta comercial)

Menu **Preços e propostas** (grupo "Na disputa"), com três abas. A aba de propostas comerciais é exclusiva dos planos **Avançado** e **Consultor**; os demais veem um convite para mudar de plano.
- **Propostas comerciais**: escolha um edital e a IA lê o que ele exige da proposta (itens, quantidades, valores estimados, validade mínima, planilha de custos, BDI, documentos, declarações). Para cada item, informe o custo ou busque em **Preços** (tabelas oficiais + Compras.gov.br pelo código CATMAT/CATSER). Defina regime tributário, tributos e BDI (há calculadora pela fórmula do Acórdão TCU 2.622/2013). O sistema calcula preços e alerta: acima do estimado (art. 59, III), abaixo de 75%/85% em obras (art. 59, §§4º e 5º) e abaixo de 50% nos demais (IN SEGES/ME 73/2022, art. 34). **Gerar minuta**: a IA redige a proposta com as condições e declarações do edital e revisa os preços. **Baixar Word**: .docx com a tabela de itens e o valor por extenso.
- **Pesquisas de preço**: as pesquisas do Compras.gov.br de antes.
- **Tabelas de referência**: busca nas tabelas oficiais carregadas.

**Administração → Tabelas de preços**: envie planilhas .xlsx/.csv (SINAPI, SICRO, CMED, SIGTAP, CCT, BPS ou outra). O sistema acha o cabeçalho e sugere as colunas de código, descrição, unidade e preço; você confirma, informa UF e data-base e importa. Desative a tabela antiga quando sair nova data-base.


## Elaboração com advogado (serviço pago)

- Em **Peças → Elaboração com advogado**: cartões com cada peça, descrição e valor. O cliente escolhe, descreve o caso, indica edital/contrato e prazo e paga pelo Mercado Pago (Checkout Pro: Pix, boleto ou cartão em até 3x). O pedido só entra na fila depois do pagamento aprovado; "Meus pedidos" mostra a situação, com opção de pagar ou cancelar pedidos não pagos.
- Numa minuta gerada pela IA, **Revisão por advogado** segue o mesmo fluxo e o mesmo valor.
- Os valores ficam em `PRECO_REVISAO` (backend/config.py). O seletor de tipo de peça não mostra mais preço.
- Admin → **Pedidos de advogado**: pagos primeiro ("pago · a fazer"), depois em andamento e aguardando pagamento. Na elaboração, escreva a peça no editor e marque "Concluída": ela aparece para o cliente com o parecer. O administrador recebe e-mail (Resend) quando um pedido é pago.
- Pagamentos de serviço entram em **Receitas** como "serviços" (sem contar em dobro com a revisão concluída).


## Gestão de contratos

- **Limites**: teste grátis 1 contrato · Essencial sem gestão · Profissional 10 · Avançado 30 · Consultor 50. **Pacote extra**: +10 contratos por R$ 169,90/mês (Plano e conta → Contratos extras), pago pelo Mercado Pago com cartão recorrente ou Pix/boleto por 1 mês. Pacote vencido: os contratos já cadastrados continuam acessíveis, mas novos acima do limite ficam bloqueados.
- **Cadastro pelo PDF**: a IA lê número, órgão, objeto, valores, vigência, prorrogação, data-base e índice de reajuste/repactuação, garantia, pagamento, medição, faturamento, fiscal/gestor, penalidades e as **obrigações periódicas** da contratada. Tudo fica editável; o cadastro manual continua disponível.
- **Agenda de gestão automática**: decidir a prorrogação (120 dias antes) e confirmar o aditivo (60 dias), fim da vigência, renovar a garantia (30 dias antes) e vencimento, preparar reajuste/repactuação (30 dias antes) e aniversário, e as próximas 3 ocorrências de cada rotina (medição, nota fiscal, comprovação de FGTS/INSS etc.), que se renovam sozinhas.
- **Aviso por e-mail**: o job diário (`jobs/radar_diario.py`, que agora roda todos os dias e chama `jobs/avisos_contratos.py`) envia a cada usuário da conta os prazos vencidos e dos próximos 7 dias, uma vez por dia. Precisa do Resend configurado; no cron do Render, preencha `RESEND_API_KEY`, `EMAIL_REMETENTE` e `FRONTEND_URL`.


## Documento do edital

Na lista de **Editais** (e no cabeçalho de cada edital), o ícone de olho abre o PDF numa nova aba, com botão de download. Vale para PDFs enviados pelo usuário e para editais capturados do PNCP: o PDF agora é guardado na importação, e os editais antigos têm o documento baixado do PNCP na primeira vez em que alguém abre. O link "Ver no PNCP" continua ao lado.

## Logs de erros (Administração → Logs de erros)

Guarda os erros que os usuários encontram: falhas do servidor (com rastreamento técnico), tarefas em segundo plano (análise de edital, leitura de contrato, proposta, radar, avisos), integrações (Mercado Pago, Resend, IA, PNCP) e erros de JavaScript/falta de conexão no navegador. Erros iguais são agrupados, com contador. Filtros por situação, origem, período e busca. **Copiar para análise** e **Baixar .txt** geram um relatório pronto para colar na conversa. Retenção de 90 dias. Nenhuma senha, token ou dado de formulário é gravado.


## Dossiê completo do concorrente

Na página do concorrente, **Montar/Atualizar dossiê completo** (conta 1 análise de concorrente do plano):
1. Consulta pública (Receita, TCU, CGU/CEIS/CNEP, contratos no PNCP).
2. **Busca automática no PNCP**: a partir dos contratos do concorrente, chega à compra de origem e baixa atas, julgamentos, decisões de recurso e relatórios que citem o CNPJ ou a razão social (até 8 compras e 12 documentos). É melhor esforço: muitos órgãos não publicam as atas no PNCP.
3. **Acervo**: o usuário junta documentos de outros certames (atas, decisões, habilitações, balanços, atestados, certidões), obtidos no portal da disputa, via LAI ou em processos. A IA lê cada um procurando só o que diz respeito à concorrente.
4. **Consolidação pela IA**: inabilitações e desclassificações anteriores, atestados conhecidos, índices contábeis, certidões, responsáveis técnicos, sanções, fragilidades recorrentes, **pontos de ataque** e lacunas, cada item com a fonte (`doc#N`, `analise#N`, dados públicos).

Nas análises de habilitação/proposta desse concorrente em um edital, a IA recebe o dossiê consolidado e devolve, além dos apontamentos, o **cruzamento com o histórico** (hipóteses a conferir) e **sugestões de peça** (recurso, contrarrazões, intenção de recorrer, pedido de diligência, representação), que podem ser marcadas e enviadas ao gerador de peças.

## Assistente virtual (chatbot de atendimento)

- Widget em `frontend/chat/` (`widget.css` + `widget.js`), carregado em todas as telas pelo `index.html`. Funciona para visitantes e para clientes logados.
- As respostas vêm de `POST /api/chat` (`backend/routes/chat.py`). A IA (rota "barata") recebe uma base oficial montada com os planos, os preços, os limites e os serviços do próprio código (`services/atendimento.py`), então muda sozinha quando os planos mudam. Sem chave de IA, ou em caso de falha, a resposta sai de regras por palavra-chave.
- **Falar com atendimento**: o visitante deixa nome, e-mail e WhatsApp. A conversa vira um chamado e os `ADMIN_EMAILS` recebem um e-mail com o histórico.
- **Administração → Atendimento**: chamados abertos, conversa completa, links de e-mail e WhatsApp, situação (aguardando, em atendimento, resolvida) e anotações internas.
- Limites: 1.200 caracteres por mensagem e 60 mensagens por conversa. A conversa fica salva no navegador; o botão ↺ começa uma nova.

## Logomarca

- O símbolo (`simboloMarca()` em `frontend/js/icones.js`) e o favicon usam a geometria exata do arquivo oficial `frontend/assets/KASISKI_logo_vetorial.pdf`. Os traços azul-noite seguem a cor do texto, então ficam brancos sobre fundos escuros.
- O logotipo completo em SVG, para e-mails, apresentações ou redes, fica em `frontend/assets/kasiski-logo.svg`.

## Possíveis concorrentes (Editais → Análise)

- Botão **Avaliar possíveis concorrentes**, separado da análise do edital. O Kasiski procura no PNCP contratos e atas de registro de preços com objeto parecido (termos sugeridos pela IA na extração, mais o núcleo do objeto) e consulta quem venceu cada um: o fornecedor do contrato ou os homologados por item.
- As empresas são ordenadas por número de vitórias, semelhança do objeto, data, mesma UF e mesmo órgão, com relevância alta, média ou baixa. Cada empresa mostra nome, CNPJ, valor contratado, onde atua e as contratações, com link para o PNCP.
- Botões: **Montar dossiê**, que abre o dossiê completo do concorrente, e **Analisar documento**, que abre a aba Concorrentes com o CNPJ já preenchido.
- **Limite mensal por plano** (recurso `possiveis` em `backend/planos.py`): Teste 1, Essencial 2, Profissional 5, Avançado 15 e Consultor 25. Cada avaliação concluída desconta 1, inclusive "Avaliar novamente". Se o PNCP não responder, nada é descontado. O uso aparece em Plano e conta e no próprio bloco do edital.
- A consulta roda em segundo plano (`POST /api/editais/<id>/possiveis-concorrentes`) e tem tempo máximo de cerca de 100 segundos.
- Código: `backend/services/possiveis_concorrentes.py` e as funções `buscar_documentos`, `fornecedor_do_contrato` e `vencedores_da_compra` em `services/pncp.py`.

## Oportunidades (Kanban do ciclo comercial)

- Nova tela **Oportunidades** (`#/oportunidades`) com um quadro de 11 etapas: Identificada → Em análise → Decisão Go / No-Go → Preparação → Pronta para disputa → Em disputa → Classificada / Habilitação → Recurso / Contrarrazões → Adjudicada / Homologada → Contratação → Contrato ativo. Há duas saídas laterais, **Perdida** e **Desistência / No-Go**, que pedem o motivo.
- O cartão mostra número, órgão, objeto, valor, sessão, responsável, fit, risco e dias para a sessão.
  - **Fit** = 70% aderência da habilitação (checklist da análise) + 30% recomendação da IA. Antes da análise, vale a nota do radar.
  - **Risco** = pior nível entre os riscos e as cláusulas restritivas.
- Ao abrir o cartão, aparece o dossiê em painel lateral: dados, UASG/unidade, datas e prazos, análise, preços e proposta, itens e lotes (PNCP), documentos e peças, concorrentes, histórico do órgão e movimentações. O painel também tem a decisão Go / No-Go e o responsável (usuário da conta ou texto livre).
- **Movimentos automáticos** (só avançam; o usuário pode mover para qualquer etapa):
  - edital capturado ou enviado → Identificada;
  - análise iniciada → Em análise; análise concluída → Decisão;
  - Go → Preparação; No-Go → Desistência;
  - sessão iniciada → Em disputa;
  - resultado registrado → Classificada; peça de recurso ou contrarrazões → Recurso;
  - PNCP com resultado homologado para a empresa → Homologada; para outra empresa → Perdida;
  - PNCP com licitação revogada ou anulada → Perdida;
  - contrato publicado no PNCP ou cadastrado na Gestão de contratos → Contrato ativo.
- A sincronização com o PNCP roda todo dia no mesmo cron do radar (`jobs/sincronizar_oportunidades.py`) e também pelo botão **Sincronizar com o PNCP**.
- O Painel ganhou o bloco **Pipeline de oportunidades**. A tela do edital tem um atalho para o cartão.
- Código: `backend/services/oportunidades.py`, `backend/routes/oportunidades.py` e `frontend/js/views/oportunidades.js`. Os dados ficam nos campos novos de `Edital` e na tabela `Movimento`, criados automaticamente.

## Máquina de aquisição (site público, CRM de leads, tracking e automações)

### Site público com URLs limpas (`site/` → `publico/`)
- As páginas são HTML estático gerado por `python site/gerar.py` (requer `pip install markdown`). **Depois de editar textos, rode o gerador de novo e publique a pasta `publico/`.**
- Páginas geradas:
  - ferramentas: `/analisar-edital/`, `/consultar-concorrente/`;
  - soluções: `/radar-licitacoes/`, `/go-no-go/`, `/concorrentes/`, `/habilitacao/`, `/precos/`, `/propostas/`, `/gestao-contratos/`;
  - outras: `/consultorias/`, `/newsletter/`, `/inteligencia/` (+ artigos), `/glossario/` (+ 10 termos), `/privacidade/`, `/cookies/`, `/termos/`, `/termos-ia/`;
  - landing pages sem menu (fora do índice do Google): `/lp/analisar-edital/`, `/lp/software-licitacoes/`, `/lp/radar/`, `/lp/consultorias/`, `/lp/concorrentes/`.
- SEO: `title`, `description`, `canonical`, Open Graph (imagem `assets/og-kasiski.png`), JSON-LD (Organization, SoftwareApplication, BreadcrumbList, DefinedTerm, Article), `sitemap.xml`, `robots.txt`, `404.html` e `_redirects` (Netlify).
- Onde editar:
  - textos em `site/conteudo.py` (soluções, landing pages, glossário e **dados do controlador para a LGPD: preencha CNPJ e endereço**);
  - textos legais em `site/legal.py`;
  - artigos em `site/artigos/*.md`.
- O app fica em `app.kasiski.com.br` (veja a seção abaixo). `/entrar` e `/cadastro` do site redirecionam para o app.

### Rastreamento (`frontend/js/rastreio.js`, usado no site e no app)
- `visitor_id` próprio, primeiro e último toque (UTMs, gclid, fbclid, li_fat_id, `?ref=` de parceiro, página de entrada, site de origem), guardados até a assinatura.
- Banner de cookies com três categorias (necessários, medição e marketing), Google Consent Mode v2 e "Preferências de cookies" no rodapé.
- **Tags:** cole os IDs em `frontend/js/config.js` → `TAGS`. O recomendado é preencher só o `GTM_ID` e configurar GA4, Google Ads, LinkedIn e Meta dentro do Tag Manager, com "consentimento adicional". Sem ID, nenhuma tag de terceiros é carregada.
- **Data Layer** (nomes padrão do GA4 quando existem):
  - no site: `page_view`, `cta_click`, `pricing_view`, `lead_form_start`, `generate_lead`, `tool_started`, `tool_completed`;
  - no app: `sign_up`, `login`, `company_created`, `radar_configured`, `edital_added`, `edital_analyzed`, `begin_checkout`, `purchase`.
- O servidor registra os mesmos eventos (e mais `document_uploaded`, `competitor_analyzed`, `proposal_generated`, `legal_document_generated`, `subscription_cancelled`) na tabela `Evento`, ligados ao lead e ao canal.

### CRM de leads e lead score (`services/marketing.py`)
- Tabela `Lead`: contato, empresa, UTMs, canal, isca, página de entrada, score, status (novo → engajado → MQL > 50 → SQL > 80 → trial → ativado → assinante, ou perdido), responsável e notas.
- No cadastro, o lead é ligado à conta pelo e-mail ou pelo `visitor_id`, e a conta guarda `aquisicao` (primeiro e último toque).
- Pontos: newsletter +2, planos +5, consulta de concorrente +10, análise gratuita +15, cadastro +20, empresa +20, radar +15, uso da IA +25, checkout +30.

### API pública (`/api/public/...`) com anti-abuso
- `analisar-edital`: upload + triagem com IA barata; a tela mostra nota, contagens e o 1º ponto, e os demais pontos **não saem do servidor**.
- `concorrente` (resumo do dossiê), `newsletter` (com confirmação por e-mail e descadastro em `/api/public/sair?t=`), `leads` e `eventos`.
- Proteções:
  - limite por IP e por e-mail e teto diário de análises (`PUBLICO_ANALISES_DIA`);
  - honeypot e Cloudflare Turnstile opcional (`TURNSTILE_SECRET` no Render + `TURNSTILE_SITEKEY` no `config.js`);
  - PDF de até 15 MB, apagado em 7 dias.
- Quem cria conta com o mesmo e-mail tem o edital importado ao cadastrar a empresa, e a análise completa roda **de cortesia** (não desconta do plano).

### Automações de e-mail (`services/automacoes.py`)
- Boas-vindas, lembrete de empresa, configurar radar, radar funcionando, 24h sem análise, 1ª análise concluída, fim do teste em 48h, 24h e 6h (com o valor acumulado da conta).
- Cada e-mail sai uma vez por conta, respeita o descadastro, roda a cada 10 min no servidor web e tem reforço no job diário.
- Em Admin → Marketing → Automações é possível ativar ou pausar, editar o assunto, enviar um teste e rodar na hora.

### Admin → Marketing
- **Funil:** visitantes → leads → trials → ativados → assinantes.
- **Indicadores:** MRR, ARR, ARPU, MRR novo, CAC, LTV, payback, churn e taxas de conversão.
- **Canais e campanhas:** CAC por canal, campanhas (utm_campaign) e cohort de retenção por canal.
- **Leads:** lista com filtros, jornada completa e exportação .csv.
- **Ferramentas grátis:** uso e custo de IA, conversão por isca e exportação da newsletter.
- **Investimentos:** gasto por canal e mês, usado no CAC.


## Dois domínios: kasiski.com.br (site) e app.kasiski.com.br (aplicativo)

| Pasta | Domínio | O que é |
|---|---|---|
| `publico/` | kasiski.com.br | Site público gerado por `python site/gerar.py`: página inicial, ferramentas grátis, soluções, conteúdo, LGPD e chat. Indexado pelo Google. |
| `frontend/` | app.kasiski.com.br | Aplicativo (login, painel e todas as telas). `robots.txt` e `noindex` o mantêm fora dos buscadores. |

- **Nunca edite `publico/` à mão.** Ele é apagado e recriado a cada geração. Os arquivos compartilhados (`js/config.js`, `js/rastreio.js`, `chat/`, `assets/`) são copiados de `frontend/`, e o estilo e o script do site vêm de `site/estatico/`.
- **Visitante, UTMs, consentimento e o pré-preenchimento do cadastro** ficam em cookies próprios no domínio `.kasiski.com.br`. Com isso, a atribuição (primeiro e último toque) passa do site para o app, e o banner de cookies aparece uma vez só. `kasiski.com.br`, `www` e `app` contam como o mesmo site, não como origem externa.
- **Links antigos** (`kasiski.com.br/#/painel`, retornos de pagamento) são redirecionados para o app. No app, `/` abre o login ou o painel, e `#/inicio` leva ao site.
- **Planos da página inicial:** os valores gerados vêm de `site/conteudo.py → PLANOS`, e a página confere preço e limites em `/api/planos` ao carregar.
- **Desenvolvimento:** app em `http://localhost:8080` (pasta `frontend`) e site em `http://localhost:8081` (pasta `publico`). O `config.js` detecta localhost.

### Migração (uma vez)

1. **Netlify, site novo do app.** Crie um site com a pasta `frontend/` (arraste a pasta ou ligue ao GitHub com *Publish directory* = `frontend`). Em *Domain management*, adicione `app.kasiski.com.br`. Como o DNS de kasiski.com.br já está no Netlify, o registro e o HTTPS saem automaticamente.
2. **Netlify, site atual (kasiski.com.br).** Troque o conteúdo publicado para a pasta `publico/` (arraste a pasta ou mude o *Publish directory* para `publico`).
3. **Render**, no serviço web e no cron:
   - `FRONTEND_URL=https://app.kasiski.com.br`;
   - `SITE_URL=https://kasiski.com.br`;
   - em `CORS_ORIGINS`, acrescente `https://app.kasiski.com.br`.
4. **Mercado Pago, Resend e webhook:** nada muda. Os links de retorno saem do backend, pelo `FRONTEND_URL`.
5. **Usuários:** entram de novo uma vez no app (a sessão fica guardada por domínio).
