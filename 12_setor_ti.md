# Contratações de Tecnologia da Informação

## Regramento federal de referência
No âmbito federal, as contratações de TI seguem a Lei 14.133 combinada com normas específicas — principalmente a Instrução Normativa SGD/ME nº 94/2022 (e as que a sucederem), que disciplina o processo de contratação de soluções de TIC pelos órgãos do Executivo Federal, com fases de planejamento (ETP, Termo de Referência), seleção do fornecedor e gestão do contrato. Estados e municípios costumam ter normas próprias equivalentes ou aplicam a Lei 14.133 diretamente; confira o edital para saber qual regramento local se soma à lei geral.

## Modelos de contratação de TI
- **Licença de uso de software (on-premise)**: aquisição do direito de uso, por prazo determinado ou perpétuo, com ou sem manutenção/atualização (garantia técnica).
- **SaaS (Software como Serviço)**: contratação de solução hospedada pelo fornecedor, remunerada por assinatura; o edital deve tratar de disponibilidade (SLA), portabilidade e devolução dos dados ao fim do contrato, e localização do datacenter quando houver exigência de dados em território nacional.
- **Desenvolvimento e fábrica de software**: remunerado por métrica de tamanho (pontos de função, story points) ou por homem-hora; a Lei 14.133 veda a contratação por postos de trabalho para atividades de desenvolvimento, salvo justificativa técnica.
- **Outsourcing/sustentação de infraestrutura**: serviço continuado, segue a lógica de dedicação de mão de obra quando há postos alocados nas dependências do contratante.
- **Aquisição de equipamentos (hardware)**: segue a lógica de fornecimento de bens, com garantia do fabricante e suporte técnico.

## Habilitação técnica específica
Além da habilitação padrão: atestados de capacidade técnica compatíveis com a métrica de contratação (não apenas "já prestou serviço de TI", mas volume/porte comparável); comprovação de certificações do fabricante (quando revenda de licenças de terceiros); certificações de processo (ISO/IEC 27001 para segurança da informação, ISO/IEC 20000 para gestão de serviços de TI, CMMI para desenvolvimento) quando exigidas — devem ser proporcionais à complexidade do objeto, sob pena de restrição indevida.

## LGPD e segurança da informação
Contratos que envolvem tratamento de dados pessoais pela contratada (operador, nos termos da LGPD) devem prever cláusulas de proteção de dados: finalidade do tratamento, medidas de segurança, notificação de incidentes, devolução ou eliminação dos dados ao fim do contrato. A ausência dessas cláusulas em objeto que claramente envolve dados pessoais sensíveis (ex.: sistema de prontuário eletrônico, folha de pagamento) é um risco a apontar, não necessariamente uma cláusula restritiva contra o licitante, mas um risco contratual relevante.

## Propriedade intelectual
Em desenvolvimento sob encomenda, o padrão é a cessão dos direitos patrimoniais sobre o código ao contratante (o código pertence à Administração). Cláusulas que deixem ambíguo quem detém a propriedade do código desenvolvido, ou que permitam à contratada reter o código-fonte como forma de garantia de pagamento, geram risco de vendor lock-in e devem ser sinalizadas.

## Pontos de atenção na análise
- Métrica de dimensionamento incompatível com o histórico de atestados exigidos (ex.: exigir 10.000 pontos de função de execução simultânea quando o mercado local raramente atende esse porte) pode ser cláusula restritiva.
- SLA com penalidades desproporcionais para disponibilidade (ex.: 99,99% sem justificativa para sistema não crítico) é ponto de risco a negociar via pedido de esclarecimento.
- Exigência de certificação de fabricante específico sem admitir "ou equivalente" pode configurar direcionamento (art. 9º).
