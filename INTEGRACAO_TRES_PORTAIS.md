# KASISKI — Compras.gov.br, BEC-SP e BBMNET

O catálogo de capacidades está disponível em `GET /api/disputas/portais/capacidades` (autenticado). O seletor da sala de disputa aceita `bbmnet`, além dos portais anteriores. Nenhum endpoint envia lances ou lê eventos autenticados em tempo real. A aprovação humana continua vinculada ao fluxo semiautomático já existente e o lance é executado no portal oficial pelo licitante.

## Habilitação real
1. Compras.gov.br: obter documentação/autorização específica para acesso de fornecedor à sessão e transmissão de lances; a API pública de dados abertos não oferece, por si só, essa capacidade.
2. BEC-SP: confirmar escopo do web service de compras e se a sessão em questão ainda opera na BEC; solicitar autorização transacional se existente.
3. BBMNET: solicitar ao operador manual oficial atualizado de integração, escopos, credenciais de homologação e autorização de operação em nome de fornecedor. A existência de manual de integração não comprova endpoint de lance.
4. Para cada portal, testar homologação, eventos, reconfirmação de preço, idempotência, recibo oficial, timeout e trilha de auditoria antes de ativar envio.

Não utilizar credenciais do fornecedor armazenadas em texto puro, automação para contornar CAPTCHA ou endpoints privados não documentados. Não declarar lance aceito sem confirmação oficial do portal.
