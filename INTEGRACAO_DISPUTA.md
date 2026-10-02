# KASISKI — segurança da automação de disputas

## O que foi adicionado
- Motor puro `backend/services/disputa_automacao.py`: valida fase, autorização, atualização dos dados, piso, status e intervalos antes de sugerir um lance.
- `POST /api/disputas/{id}/automacao/simular`: endpoint autenticado, limitado à empresa e ao plano, **sem envio** de lances. Como não há conector autenticado de eventos, retorna bloqueio por dados não confirmados.
- `GET /api/disputas/automacao/capacidades`: informa explicitamente as capacidades disponíveis.
- Sala manual, registro histórico e interface existentes preservados.

## Antes de liberar execução real
1. Obter documentação, contrato ou autorização expressa do operador do portal.
2. Implementar um adaptador oficial para leitura de eventos e envio, com testes em homologação.
3. Vincular autorização do representante da empresa ao pregão e item específico; exigir revogação imediata.
4. Usar travas transacionais no servidor, idempotência, limitação de frequência, atualização confirmada e trilha imutável.
5. Confirmar regras do edital e do portal, especialmente critério de julgamento, decremento, intervalos e fase.
6. Não utilizar scraping autenticado, CAPTCHA bypass ou endpoints internos não documentados como meio de envio.

## Implantação
Publicar backend no Render pelo fluxo atual. Não são necessárias novas variáveis. Os endpoints não habilitam automação real. Frontend e site permanecem iguais.
