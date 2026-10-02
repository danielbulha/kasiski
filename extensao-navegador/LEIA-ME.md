# Extensão Kasiski — Sala de Disputa (Chrome/Edge)

Lê a sala de disputa do **Compras.gov.br** que o usuário abriu no próprio navegador, com o próprio login, e envia ao
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

## Arquivos
- `manifest.json` — Manifest V3. Permissões: `storage`, a API do Kasiski e a sala do Compras.gov.br.
- `config.js` — endereço da API (troque para `http://127.0.0.1:5000` ao testar com o backend local).
- `adaptadores/comprasgov.js` — **onde ficam os dados na página**. Seletores levantados no código público do
  aplicativo do portal (componentes `app-disputa-fornecedor*` e atributos `data-test` como `valor-geral`,
  `valor-fornec`, `situacao-item`). Ainda precisam ser conferidos numa sala real.
- `observador.js` — compara as leituras e gera os eventos; inclui "Copiar estrutura da página (sem números)".
- `background.js` — guarda a conexão, junta os eventos e envia à API (tenta de novo se a rede cair).
- `popup.html` / `popup.js` — conectar, ver o estado e desconectar.

## Adaptador do Compras.gov.br
A sala do fornecedor fica em `https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/seguro/fornecedor/disputa`
(aplicativo Angular, atualizado por websocket). O que a extensão lê em cada item (`.cp-itens-disputa`):

| Dado | Onde |
|---|---|
| Número do item | `app-identificacao-item .dots > span` |
| Melhor valor | `[data-test="valor-geral"]` |
| Meu valor | `[data-test="valor-fornec"]` |
| Fase | `[data-test="situacao-item"]` |
| Ganhando / perdendo / empatado | ícone `fa-thumbs-up` / `fa-thumbs-down` / `fa-hand-paper` (texto no `title`) |
| Tempo restante | `[data-test="tempo-restante"]` |
| Mensagens do chat | `.cp-mensagens-compra` (`.mensagens-texto`, `.mensagens-data`) |

O portal mostra "ganhando/perdendo", não a posição numérica: essa situação vai junto com a fase.
**Conferir na primeira sessão real:** abra a sala, clique em **Copiar estrutura da página (sem números)** no ícone
da extensão e compare com a tabela. Se o portal mudar, só `adaptadores/comprasgov.js` precisa ser atualizado.

## Instalar em modo desenvolvedor
Chrome/Edge → `chrome://extensions` → ative **Modo do desenvolvedor** → **Carregar sem compactação** → escolha esta pasta.

## Backend
- `POST /api/disputas/<id>/extensao/codigo` (login) — gera o código.
- `GET|DELETE /api/disputas/<id>/extensao` (login) — estado / desconectar.
- `POST /api/extensao/vincular` — troca o código pelo token (limite por IP).
- `POST /api/extensao/eventos` com `Authorization: Extensao <token>` — até 100 eventos por envio, 600 por minuto.
  Evento: `{id, tipo: melhor_lance|meu_lance|posicao|fase|mensagem, item, valor?, texto?, visto_em}`.
  O `id` evita duplicados; o mesmo valor relido não vira lance novo; CNPJ/CPF nas mensagens são omitidos.
- Tabelas novas `vinculo_extensao` e `evento_disputa`, criadas no boot pelo `db.create_all()`.
