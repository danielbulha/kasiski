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
- `adaptadores/comprasgov.js` — **onde ficam os dados na página**. Os seletores ainda estão vazios: falta uma
  cópia da sala de disputa logada. Enquanto vazios, a extensão mostra "aguardando configuração" e não envia nada.
- `observador.js` — compara as leituras e gera os eventos; inclui "Copiar estrutura da página (sem números)".
- `background.js` — guarda a conexão, junta os eventos e envia à API (tenta de novo se a rede cair).
- `popup.html` / `popup.js` — conectar, ver o estado e desconectar.

## Configurar o adaptador do Compras.gov.br
1. Instale a extensão em modo desenvolvedor (abaixo) e abra uma sala de disputa (ou de teste) no Compras.gov.br.
2. No ícone da extensão, clique em **Copiar estrutura da página (sem números)**. Todos os dígitos viram `9` e e-mails
   são omitidos; revise o conteúdo (nomes de empresas podem aparecer) antes de enviar ao time do Kasiski.
3. Preencha `SELETORES_COMPRASGOV` com os seletores CSS de cada informação.
4. Confirme o endereço da sala em `manifest.json` (`content_scripts.matches`). O valor atual,
   `https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/*`, precisa ser conferido com a URL real da sala.

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
