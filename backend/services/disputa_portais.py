"""Catálogo de integração da sala de disputa.

Nenhum conector transacional está autorizado/configurado nesta versão.
As URLs são portais oficiais para execução manual, não endpoints de envio.
"""
PORTAIS = {
    'comprasgov': {'nome':'Compras.gov.br','url':'https://www.gov.br/compras/pt-br', 'consulta_publica':True, 'eventos_ao_vivo':False, 'envio_lance':False, 'estado':'aguardando_api_transacional_autorizada'},
    'bec': {'nome':'BEC-SP','url':'https://www.bec.sp.gov.br/', 'consulta_publica':True, 'eventos_ao_vivo':False, 'envio_lance':False, 'estado':'webservice_publico_nao_transacional'},
    'bbmnet': {'nome':'BBMNET (Bolsa Brasileira de Mercadorias)','url':'https://bbmnet.com.br/', 'consulta_publica':True, 'eventos_ao_vivo':False, 'envio_lance':False, 'estado':'solicitar_escopo_e_credenciais_de_integracao'},
}

def capacidades(portal):
    return dict(PORTAIS.get(portal, {'nome':portal, 'consulta_publica':False,'eventos_ao_vivo':False,'envio_lance':False,'estado':'nao_configurado'}))
