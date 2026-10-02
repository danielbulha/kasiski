# Extensão Kasiski — Sala de Disputa (Chrome/Edge)

Lê a sala de disputa dos portais de licitação que o usuário abriu no próprio navegador, com o próprio login, e envia ao
Kasiski o que muda na tela: melhor lance, o lance do usuário, posição, fase e mensagens do pregoeiro. A sala de
disputa do Kasiski se atualiza sozinha.

**O que ela não faz:** não envia lances, não clica, não preenche campos, não lê cookies nem senhas do portal.
Os dados são "lidos da tela do portal", não uma confirmação oficial. O usuário confere na sala oficial antes de lançar.

> **Regras do portal:** antes de distribuir a extensão a clientes, confirme nos termos de uso do Compras.gov.br
> (e com o jurídico) que a leitura automatizada da própria tela é permitida.

## Como funciona
1. Na sala de disputa do Kasiski, o usuário clica em **Conectar extensão** e recebe um código (`ABCD-1234`, vale 10 min, uso único).
2. Digita o código no ícone da extensão. A extensão recebe um token próprio (12 h), guardado só na sessão do navegador.
   O token serve apenas para enviar eventos das salas daquela licitação; não dá acesso ao resto do Kasiski.
3. Com a sala oficial aberta, `observador.js` lê a página a cada mudança (e a cada 2 s) e manda só o que mudou.
4. A conexão cai quando o usuário clica em Desconectar (na extensão ou no Kasiski), troca a senha, exclui a sala ou o token expira.

## Portais

| Portal | Sala | Leitura |
|---|---|---|
| Compras.gov.br | `cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/disputa` | configurada (código público do portal) |
| BBMNET | `sala.bbmnet.com.br` | configurada (código público do portal) |
| BLL Compras | `bllcompras.com` | aguardando captura |
| BNC Compras | `bnccompras.com` | aguardando captura |
| Portal de Compras Públicas | `operacao.portaldecompraspublicas.com.br` | aguardando captura |
| BEC-SP | `www.bec.sp.gov.br` | aguardando captura |
| Licitanet | `portal.licitanet.com.br` | aguardando captura |
| Licitações-e | `www.licitacoes-e.com.br`, `licitacoes-e2.bb.com.br` | aguardando captura |

"Configurada" ainda precisa ser conferida numa sala real. "Aguardando captura": a extensão já tem permissão no portal,
mas mostra "a leitura deste portal ainda está sendo configurada" e não envia nada.

### Onde fica a configuração
`backend/data/adaptadores_extensao.json` (servido em `GET /api/extensao/adaptadores`). A extensão baixa esse arquivo e o
guarda por 1 hora; sem rede, usa a cópia `adaptadores/padrao.json`. **São só dados** (seletores CSS e nomes de colunas),
nunca código, o que a Chrome Web Store permite atualizar sem nova revisão. Dois tipos de leitura:

- `seletores`: um seletor por informação dentro de cada item (`item`, `itemNumero`, `melhorLance`, `meuLance`, `fase`,
  `situacao`). Usado no Compras.gov.br.
- `tabela`: acha a coluna pelo texto do cabeçalho (`colunas: {"item": "Lote / Item", "melhorLance": "Melhor proposta / Lance"}`)
  e lê a célula de mesma posição em cada linha. Usado no BBMNET.

`mensagens` (opcional): `mensagem`, `hora`, `texto`, `item`.

### Liberar a leitura de um portal
1. Um usuário conecta a extensão, abre a sala de disputa do portal e clica em **Copiar estrutura da página (sem números)**.
2. Com a estrutura, preencha o `leitura` (e `mensagens`) do portal em `backend/data/adaptadores_extensao.json` e copie o
   arquivo para `adaptadores/padrao.json`.
3. Publique o backend: em até 1 hora todas as extensões instaladas passam a ler o portal, sem nova versão na loja.
4. Portal **novo** (endereço que não está no `manifest.json`) exige nova versão da extensão na loja.

## Arquivos
- `manifest.json` — Manifest V3. Permissões: `storage`, a API do Kasiski, o aplicativo do Kasiski e as salas dos portais.
- `config.js` — endereço da API (troque para `http://127.0.0.1:5000` ao testar com o backend local).
- `motor.js` — aplica a configuração do portal na página (só leitura).
- `adaptadores/padrao.json` — cópia da configuração dos portais que vai dentro da extensão.
- `observador.js` — compara as leituras e envia só o que mudou; inclui "Copiar estrutura da página (sem números)".
- `background.js` — guarda a conexão, baixa a configuração dos portais e envia os eventos à API.
- `ponte-kasiski.js` — conexão com um clique a partir do aplicativo do Kasiski.
- `popup.html` / `popup.js` — conectar, ver o estado e desconectar.
- `empacotar.py` — gera o .zip para a loja e confere configuração × permissões.

## Publicar na Chrome Web Store (para o botão "Instalar extensão")
O Chrome só instala extensões vindas da loja. Depois de publicada, o botão **Instalar extensão** do Kasiski abre a página
dela na loja e o usuário clica em "Usar no Chrome".

1. Gere o pacote: `python3 empacotar.py` → `dist/kasiski-sala-de-disputa-<versão>.zip` (sem os endereços de teste local).
2. Crie a conta de desenvolvedor em https://chrome.google.com/webstore/devconsole com o e-mail da empresa
   (taxa única de US$ 5) e verifique o e-mail de contato.
3. **Novo item** → envie o .zip. Preencha:
   - **Descrição:** o que ela faz e, em destaque, que *não envia lances, não clica e não preenche nada no portal*.
   - **Ícone 128×128:** `icones/icone-128.png`. **Capturas de tela:** 1280×800 da sala do Kasiski com a extensão conectada.
   - **Finalidade única:** "Mostrar no Kasiski os dados da sala de disputa dos portais de licitação aberta pelo usuário."
   - **Justificativa das permissões:**
     `storage`: guardar a conexão com o Kasiski durante a sessão do navegador.
     Acesso às salas dos portais (Compras.gov.br, BBMNET, BLL, BNC, Portal de Compras Públicas, BEC-SP, Licitanet, Licitações-e): ler a sala de disputa aberta pelo usuário.
     Acesso a `app.kasiski.com.br`: avisar o Kasiski que a extensão está instalada e conectar com um clique.
     Acesso à API do Kasiski: enviar os dados lidos para a sala do usuário.
   - **Código remoto:** não usa.
   - **Dados do usuário:** marca "conteúdo do site" (valores e mensagens da sala); não vende nem transfere a terceiros.
   - **Política de privacidade:** URL da página de privacidade do Kasiski, com um parágrafo sobre a extensão.
   - **Visibilidade:** "Não listado" (só quem tem o link instala) ou "Público".
4. Envie para revisão (costuma levar de alguns dias a algumas semanas).
5. Publicada, copie o endereço da página da extensão para `EXTENSAO_URL_CHROME` em `frontend/js/config.js` e publique o
   aplicativo. Para o Edge, o mesmo .zip vai em https://partner.microsoft.com/dashboard/microsoftedge → `EXTENSAO_URL_EDGE`.

## Instalar em modo desenvolvedor (testes)
Chrome/Edge → `chrome://extensions` → ative **Modo do desenvolvedor** → **Carregar sem compactação** → escolha esta pasta.

## Conexão com um clique
`ponte-kasiski.js` roda só em `app.kasiski.com.br`: marca `<html data-kasiski-extensao="versão">` e, quando o usuário
clica em **Conectar a extensão**, recebe da página o código gerado pelo próprio usuário logado e conecta sem digitar.
Uma extensão recém-instalada só aparece para a página depois que ela é recarregada (botão **Já instalei**).

## Backend
- `POST /api/disputas/<id>/extensao/codigo` (login) — gera o código.
- `GET|DELETE /api/disputas/<id>/extensao` (login) — estado / desconectar.
- `GET /api/extensao/adaptadores` — configuração de leitura dos portais (pública, cache de 15 min).
- `POST /api/extensao/vincular` — troca o código pelo token (limite por IP).
- `POST /api/extensao/eventos` com `Authorization: Extensao <token>` — até 100 eventos por envio, 600 por minuto.
  Evento: `{id, tipo: melhor_lance|meu_lance|posicao|fase|mensagem, item, valor?, texto?, visto_em}`.
  O `id` evita duplicados; o mesmo valor relido não vira lance novo; CNPJ/CPF nas mensagens são omitidos.
- Tabelas novas `vinculo_extensao` e `evento_disputa`, criadas no boot pelo `db.create_all()`.
