"""Fluxo auditável de confirmação humana. NÃO envia lances aos portais."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from extensions import db, ErroAPI
from models import PropostaLance
from services.disputa import sugerir

TTL = 60

def _snapshot(d):
    return {"status": d.status, "melhor_lance": d.melhor_lance,
            "meu_ultimo": d.meu_ultimo, "preco_piso": d.preco_piso,
            "criterio": d.criterio, "melhor_em": d.melhor_em.isoformat() if d.melhor_em else None,
            "meu_ultimo_em": d.meu_ultimo_em.isoformat() if d.meu_ultimo_em else None,
            "estrategia": d.estrategia, "diferenca_minima": d.diferenca_minima}

def _json(p):
    return {"id": p.id, "disputa_id": p.disputa_id, "valor": float(p.valor),
            "estado": p.estado, "criterio": p.criterio, "criado_em": p.criado_em.isoformat(),
            "expira_em": p.expira_em.isoformat(), "decidido_em": p.decidido_em.isoformat() if p.decidido_em else None,
            "confirmado_em": p.confirmado_em.isoformat() if p.confirmado_em else None,
            "observacao": p.observacao, "envio_real": False}

def _validar(d, valor):
    if d.status != "em_disputa":
        raise ErroAPI("A disputa não está na fase competitiva.", 409)
    if d.preco_piso is None or d.melhor_lance is None:
        raise ErroAPI("Informe o piso e o melhor lance observado no portal.", 409)
    s = sugerir(d)
    if s.get("espera_s", 0) > 0:
        raise ErroAPI("Aguarde o intervalo entre lances configurado.", 409)
    try:
        v = Decimal(str(valor))
        piso = Decimal(str(d.preco_piso))
        melhor = Decimal(str(d.melhor_lance))
        minimo = Decimal(str(d.diferenca_minima or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ErroAPI("Valor inválido.", 400)
    if not v.is_finite() or v <= 0 or v.as_tuple().exponent < -2:
        raise ErroAPI("Informe um valor positivo com até duas casas decimais.", 400)
    if d.criterio == "maior_desconto":
        if v > piso or v <= melhor or v - melhor < minimo:
            raise ErroAPI("Desconto incompatível com o teto ou com o melhor lance/intervalo.", 409)
    elif v < piso or v >= melhor or melhor - v < minimo:
        raise ErroAPI("Preço incompatível com o piso ou com o melhor lance/intervalo.", 409)
    return v

def propor(d, usuario_id, payload):
    valor = payload.get("valor")
    if valor is None:
        valor = sugerir(d).get("proximo")
    v = _validar(d, valor)
    agora = datetime.utcnow()
    p = PropostaLance(disputa_id=d.id, usuario_id=usuario_id, valor=v, criterio=d.criterio,
                      snapshot=_snapshot(d), criado_em=agora, expira_em=agora + timedelta(seconds=TTL))
    db.session.add(p)
    db.session.commit()
    return _json(p)

def listar(d):
    return [_json(p) for p in PropostaLance.query.filter_by(disputa_id=d.id).order_by(PropostaLance.id.desc()).limit(30).all()]

def decidir(d, pid, usuario_id, acao, observacao=None):
    if acao not in ("aprovar", "rejeitar", "registrar_envio_manual"):
        raise ErroAPI("Ação inválida.", 400)
    p = PropostaLance.query.filter_by(id=pid, disputa_id=d.id).with_for_update().first()
    if not p:
        raise ErroAPI("Proposta não encontrada.", 404)
    agora = datetime.utcnow()
    if p.usuario_id != usuario_id:
        raise ErroAPI("Somente quem criou a proposta pode confirmá-la.", 403)
    if acao == "registrar_envio_manual":
        if p.estado != "aprovada":
            raise ErroAPI("A proposta precisa estar aprovada.", 409)
        # Registro declaratório: usuário confirma ter enviado NO PORTAL; sem envio externo.
        if not observacao or not str(observacao).strip():
            raise ErroAPI("Informe a referência ou confirmação do envio realizado no portal.", 400)
        p.estado = "envio_manual_declarado"
        p.confirmado_em = agora
        p.observacao = str(observacao)[:500]
    else:
        if p.estado != "pendente":
            raise ErroAPI("Proposta já decidida.", 409)
        if acao == "aprovar":
            if agora >= p.expira_em or _snapshot(d) != p.snapshot:
                p.estado = "expirada"
                db.session.commit()
                raise ErroAPI("A proposta expirou ou a disputa mudou. Gere outra proposta.", 409)
            _validar(d, p.valor)
            p.estado = "aprovada"
        else:
            p.estado = "rejeitada"
        p.decidido_em = agora
        p.observacao = str(observacao or "")[:500]
    db.session.commit()
    return _json(p)
