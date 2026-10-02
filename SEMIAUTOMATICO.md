# KASISKI — sala de disputa semiautomática

O botão **Revisar lance** permite alterar o valor sugerido, criar proposta persistida e aprovar ou rejeitar expressamente. O backend verifica fase, piso/teto, melhor lance e intervalo mínimo, além de revalidar o estado da disputa na aprovação. A proposta expira em 60 segundos. A aprovação não transmite lances. O usuário deve lançar no portal e usar **Dei este lance** para registrar o que efetivamente ocorreu.

Rotas autenticadas (plano com disputa):
- POST `/api/disputas/<id>/semiautomatico/propor` com `{ "valor": 92400 }` (valor opcional para sugestão atual).
- GET `/api/disputas/<id>/semiautomatico/propostas`.
- POST `/api/disputas/<id>/semiautomatico/<pid>/decidir` com `{ "acao": "aprovar" | "rejeitar" }`.
- Ação opcional `registrar_envio_manual` exige observação; é declaratória e NÃO é confirmação do portal.

Persistência: nova tabela `proposta_lance`, criada pelo `db.create_all()` no boot, desde que o usuário do banco tenha permissão de criar tabelas. Verifique backup, permissões e ambiente de homologação antes de implantar.

Limites: sem feed autenticado, a atualização dos lances concorrentes continua manual; não há envio de lances, comprovante oficial, nem integração transacional. A aprovação pode se tornar obsoleta após 60 segundos; confira a sala oficial imediatamente antes de lançar. Não confundir aprovação interna com lance aceito.
