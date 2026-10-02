"""Extensão do navegador da sala de disputa (Compras.gov.br primeiro).

A extensão roda no navegador do usuário, na sala oficial em que ele já entrou, e só LÊ o que aparece na tela:
melhor lance, o lance dele, posição, fase e mensagens do pregoeiro. Ela nunca clica, preenche ou envia lance.
Aqui o Kasiski recebe esses eventos, evita duplicados e atualiza a sala de disputa. A fonte de cada dado fica
registrada como "tela do portal": não é confirmação oficial do portal.

Vínculo: o usuário gera um código curto na sala do Kasiski (vale 10 min) e digita na extensão, que troca o código
por um token próprio (12 h). O token só serve para enviar eventos das salas desta licitação e cai se o usuário
desconectar, trocar a senha ou a sala for excluída.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from extensions import ErroAPI, db
from models import Disputa, EventoDisputa, Usuario, VinculoExtensao

CODIGO_MIN = 10
TOKEN_HORAS = 12
MAX_EVENTOS_REQ = 100
MAX_EVENTOS_MIN = 600
TIPOS = {"melhor_lance", "meu_lance", "posicao", "fase", "mensagem"}
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I, que se confundem ao digitar
_DOC = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")  # CNPJ / CPF


_ADAPTADORES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "adaptadores_extensao.json")


def adaptadores():
    """Onde a extensão lê os dados em cada portal (só dados: seletores e nomes de colunas, nunca código)."""
    with open(_ADAPTADORES, encoding="utf-8") as f:
        return json.load(f)


def portais_com_leitura():
    return {p["id"] for p in adaptadores()["portais"] if p.get("leitura")}


def _hash(v):
    return hashlib.sha256((v or "").encode()).hexdigest()


def _agora():
    return datetime.utcnow()


def _norm_item(v):
    """'Item 3', '003', 'Lote 3' -> '3'. Sem número, o texto em minúsculas."""
    s = str(v or "").strip().lower()
    n = re.findall(r"\d+", s)
    return str(int(n[0])) if n else s


def mascarar_documentos(texto):
    """Mensagens do pregoeiro podem citar CNPJ/CPF de outros licitantes: não guardamos esses números."""
    return _DOC.sub("[documento omitido]", texto or "")


def salas_do_vinculo(v):
    """A sala que gerou o código e as outras salas abertas da mesma licitação (cada item é uma sala)."""
    d = Disputa.query.get(v.disputa_id)
    if not d or d.excluido_em:
        return []
    if not d.edital_id:
        return [d]
    return Disputa.query.filter(Disputa.empresa_id == d.empresa_id, Disputa.edital_id == d.edital_id,
                                Disputa.excluido_em.is_(None)).order_by(Disputa.id).all()


def gerar_codigo(disputa, usuario, conta_id):
    codigo = "".join(secrets.choice(_ALFABETO) for _ in range(8))
    v = VinculoExtensao(conta_id=conta_id, usuario_id=usuario.id, disputa_id=disputa.id,
                        codigo_hash=_hash(codigo), codigo_expira_em=_agora() + timedelta(minutes=CODIGO_MIN),
                        token_versao_usuario=usuario.token_versao or 0)
    db.session.add(v)
    db.session.commit()
    return {"codigo": f"{codigo[:4]}-{codigo[4:]}", "expira_em": v.codigo_expira_em.isoformat(timespec="seconds")}


def vincular(codigo):
    """Troca o código (uso único) pelo token da extensão."""
    limpo = re.sub(r"[^A-Z0-9]", "", str(codigo or "").upper())
    v = VinculoExtensao.query.filter_by(codigo_hash=_hash(limpo)).first() if len(limpo) == 8 else None
    if not v or v.revogado_em or v.token_hash or not v.codigo_expira_em or v.codigo_expira_em < _agora():
        raise ErroAPI("Código inválido ou expirado. Gere outro na sala de disputa do Kasiski.", 400, "codigo_invalido")
    salas = salas_do_vinculo(v)
    if not salas:
        raise ErroAPI("A sala de disputa deste código não existe mais.", 404)
    token = secrets.token_urlsafe(32)
    v.token_hash, v.token_expira_em, v.codigo_hash = _hash(token), _agora() + timedelta(hours=TOKEN_HORAS), None
    db.session.commit()
    return {"token": token, **resumo_vinculo(v, salas)}


def resumo_vinculo(v, salas=None):
    salas = salas if salas is not None else salas_do_vinculo(v)
    from models import Edital
    d0 = salas[0] if salas else None
    ed = Edital.query.get(d0.edital_id) if d0 and d0.edital_id else None
    return {"expira_em": v.token_expira_em.isoformat(timespec="seconds") if v.token_expira_em else None,
            "licitacao": {"numero": ed.numero, "orgao": ed.orgao} if ed else None,
            "salas": [{"id": d.id, "item": d.item, "descricao": (d.descricao or "")[:120], "criterio": d.criterio,
                       "portal": d.portal} for d in salas]}


def vinculo_do_token(cabecalho):
    """Authorization: Extensao <token>."""
    if not (cabecalho or "").startswith("Extensao "):
        raise ErroAPI("Extensão não conectada.", 401, "extensao_desconectada")
    v = VinculoExtensao.query.filter_by(token_hash=_hash(cabecalho[9:].strip())).first()
    u = Usuario.query.get(v.usuario_id) if v else None
    if not v or v.revogado_em or not v.token_expira_em or v.token_expira_em < _agora() or not u \
            or (u.token_versao or 0) != (v.token_versao_usuario or 0) or not _acesso(u, v.conta_id):
        raise ErroAPI("A conexão da extensão expirou. Gere um novo código na sala de disputa.", 401, "extensao_desconectada")
    return v


def _acesso(u, conta_id):
    from auth import tem_acesso
    return tem_acesso(u, conta_id)   # saiu da equipe: a extensão para de enviar


def revogar(v):
    v.revogado_em = v.revogado_em or _agora()


def revogar_da_disputa(disputa):
    """Desconecta todas as extensões ligadas a esta sala ou às salas irmãs da mesma licitação."""
    ids = [d.id for d in (Disputa.query.filter_by(empresa_id=disputa.empresa_id, edital_id=disputa.edital_id).all()
                          if disputa.edital_id else [disputa])]
    n = 0
    for v in VinculoExtensao.query.filter(VinculoExtensao.disputa_id.in_(ids), VinculoExtensao.revogado_em.is_(None)):
        revogar(v)
        n += 1
    return n


def _data(v):
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def _numero(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n and 0 < n < 1e13 else None   # descarta NaN, zero/negativo e lixo


def receber(v, eventos):
    """Grava os eventos novos e aplica na sala. Devolve contagens e as salas atualizadas."""
    from services import disputa as D
    if not isinstance(eventos, list):
        raise ErroAPI("Envie a lista de eventos.")
    if len(eventos) > MAX_EVENTOS_REQ:
        raise ErroAPI(f"No máximo {MAX_EVENTOS_REQ} eventos por envio.", 413)
    agora = _agora()
    recentes = EventoDisputa.query.filter(EventoDisputa.vinculo_id == v.id,
                                          EventoDisputa.recebido_em >= agora - timedelta(minutes=1)).count()
    if recentes + len(eventos) > MAX_EVENTOS_MIN:
        raise ErroAPI("Muitos eventos em pouco tempo. Aguarde alguns segundos.", 429, "limite_eventos")
    salas = salas_do_vinculo(v)
    if not salas:
        revogar(v)
        db.session.commit()
        raise ErroAPI("A sala de disputa foi excluída.", 401, "extensao_desconectada")
    por_item = {_norm_item(d.item): d for d in salas}
    chaves = {str(e.get("id") or "")[:64] for e in eventos if isinstance(e, dict)}
    ja = {(x.disputa_id, x.chave) for x in EventoDisputa.query.filter(
        EventoDisputa.disputa_id.in_([d.id for d in salas]), EventoDisputa.chave.in_(chaves or {""}))}
    aceitos = duplicados = ignorados = 0
    tocadas = {}
    for e in eventos:
        if not isinstance(e, dict) or e.get("tipo") not in TIPOS or not str(e.get("id") or "").strip():
            ignorados += 1
            continue
        chave = str(e["id"])[:64]
        sem_item = e.get("item") in (None, "")
        if sem_item and e["tipo"] == "mensagem":
            alvos = salas   # aviso geral do pregoeiro: vale para todos os itens desta licitação
        else:
            d = por_item.get(_norm_item(e.get("item"))) if not sem_item else (salas[0] if len(salas) == 1 else None)
            alvos = [d] if d else []
        if not alvos:
            ignorados += 1   # item que o usuário não abriu no Kasiski
            continue
        if all((d.id, chave) in ja for d in alvos):
            duplicados += 1
            continue
        for d in alvos:
            if (d.id, chave) in ja:
                continue
            aceito = _aplicar_evento(v, d, e, chave, agora, D)
            if aceito:
                ja.add((d.id, chave))
                tocadas[d.id] = d
        if aceito:
            aceitos += 1
        else:
            ignorados += 1
    v.ultimo_evento_em = agora
    db.session.commit()
    return {"aceitos": aceitos, "duplicados": duplicados, "ignorados": ignorados,
            "salas": [{"id": d.id, "item": d.item, "melhor_lance": d.melhor_lance, "meu_ultimo": d.meu_ultimo,
                       "posicao": d.posicao} for d in tocadas.values()]}


def _aplicar_evento(v, d, e, chave, agora, D):
    """Aplica um evento na sala e grava o registro. Devolve False se o evento não tem dado aproveitável."""
    tipo, valor, texto = e["tipo"], _numero(e.get("valor")), None
    if tipo in ("melhor_lance", "meu_lance"):
        if valor is None:
            return False
        atual = d.melhor_lance if tipo == "melhor_lance" else d.meu_ultimo
        if atual is None or abs(atual - valor) >= 0.005:   # mesmo valor relido na tela não vira lance novo
            D.registrar_lance(d, valor, "mercado" if tipo == "melhor_lance" else "meu", "lido da tela do portal pela extensão")
    elif tipo == "posicao":
        if valor is None or valor > 9999:
            return False
        d.posicao = int(valor)
    elif tipo == "fase":
        texto = re.sub(r"\s+", " ", str(e.get("texto") or "")).strip()[:120]
        if not texto:
            return False
        if d.status == "preparando" and not re.search(r"encerr|suspens|aguard|agend", texto, re.I):
            d.status = "em_disputa"
    else:  # mensagem
        texto = mascarar_documentos(re.sub(r"\s+", " ", str(e.get("texto") or "")).strip())[:1000]
        if not texto:
            return False
    db.session.add(EventoDisputa(disputa_id=d.id, vinculo_id=v.id, chave=chave, tipo=tipo, valor=valor, texto=texto,
                                 visto_em=_data(e.get("visto_em")) or agora))
    return True


def estado(disputa):
    """Para a tela da sala no Kasiski: conexão ativa, última leitura, fase e mensagens recentes."""
    agora = _agora()
    ids = [d.id for d in (Disputa.query.filter_by(empresa_id=disputa.empresa_id, edital_id=disputa.edital_id).all()
                          if disputa.edital_id else [disputa])]
    ativo = VinculoExtensao.query.filter(VinculoExtensao.disputa_id.in_(ids), VinculoExtensao.revogado_em.is_(None),
                                         VinculoExtensao.token_hash.isnot(None), VinculoExtensao.token_expira_em > agora) \
        .order_by(VinculoExtensao.id.desc()).first()
    fase = EventoDisputa.query.filter_by(disputa_id=disputa.id, tipo="fase").order_by(EventoDisputa.id.desc()).first()
    msgs = EventoDisputa.query.filter_by(disputa_id=disputa.id, tipo="mensagem").order_by(EventoDisputa.id.desc()).limit(20).all()
    ultimo = EventoDisputa.query.filter_by(disputa_id=disputa.id).order_by(EventoDisputa.id.desc()).first()
    return {"conectada": bool(ativo),
            "expira_em": ativo.token_expira_em.isoformat(timespec="seconds") if ativo else None,
            "ultima_leitura_em": ultimo.recebido_em.isoformat(timespec="seconds") if ultimo else None,
            "fase": fase.texto if fase else None,
            "mensagens": [m.to_dict() for m in msgs]}
