"""Regras de cobrança: o que acontece com a conta quando o Mercado Pago avisa de um pagamento
ou de uma mudança na assinatura. Tudo idempotente — o mesmo aviso pode chegar várias vezes."""
import calendar
from datetime import datetime

from flask import current_app

import planos
from extensions import db
from models import Cobranca, Conta
from services import mercadopago as mp

STATUS_PAGAMENTO = {"approved": "aprovado", "authorized": "pendente", "pending": "pendente", "in_process": "pendente",
                    "in_mediation": "pendente", "rejected": "recusado", "cancelled": "cancelado",
                    "refunded": "estornado", "charged_back": "estornado"}
STATUS_ASSINATURA = {"pending": "pendente", "authorized": "ativa", "paused": "pausada", "cancelled": "cancelada"}
MEIOS = {"bank_transfer": "pix", "ticket": "boleto", "credit_card": "cartao", "debit_card": "cartao",
         "account_money": "saldo_mp", "prepaid_card": "cartao"}


def referencia(conta, plano, ciclo, metodo):
    return f"k:{conta.id}:{plano}:{ciclo}:{metodo}"


def ler_referencia(ref):
    """'k:12:profissional:mensal:avulso' -> (12, 'profissional', 'mensal', 'avulso')"""
    try:
        k, cid, plano, ciclo, metodo = (ref or "").split(":")
        if k != "k" or plano not in planos.PAGOS:
            return None
        return int(cid), plano, ciclo, metodo
    except ValueError:
        return None


def somar_meses(dt, meses):
    m = dt.month - 1 + meses
    ano, mes = dt.year + m // 12, m % 12 + 1
    return dt.replace(year=ano, month=mes, day=min(dt.day, calendar.monthrange(ano, mes)[1]))


def _data_mp(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def ativar(conta, plano, ciclo, metodo):
    conta.plano = plano
    conta.ciclo = ciclo
    conta.metodo_pagamento = metodo
    conta.assinatura_status = "ativa"
    conta.cancelado_em = None
    conta.assinante_desde = conta.assinante_desde or datetime.utcnow()
    from services import marketing
    marketing.evento_conta(conta, "purchase", {"plano": plano, "ciclo": ciclo, "metodo": metodo})


def estender_acesso(conta, ciclo):
    agora = datetime.utcnow()
    base = conta.pago_ate if conta.pago_ate and conta.pago_ate > agora else agora
    conta.pago_ate = somar_meses(base, 12 if ciclo == "anual" else 1)


# ---------------------------------------------------------------- processamento dos avisos
def processar_pagamento(pid):
    """Consulta o pagamento no Mercado Pago e grava/atualiza a Cobranca. Se aprovado pela primeira
    vez, estende o acesso da conta por um ciclo."""
    p = mp.pagamento(pid)
    if str(p.get("external_reference") or "").startswith("r:"):
        return processar_servico(pid, p)
    sub = ((p.get("point_of_interaction") or {}).get("transaction_data") or {}).get("subscription_id") \
        or (p.get("metadata") or {}).get("preapproval_id")
    if str(p.get("external_reference") or "").startswith("p:") or \
            (sub and Conta.query.filter_by(pacotes_mp_assinatura_id=sub).first()):
        return processar_pacote(pid, p, sub)
    ref = ler_referencia(p.get("external_reference"))
    assin_id = ((p.get("point_of_interaction") or {}).get("transaction_data") or {}).get("subscription_id") \
        or (p.get("metadata") or {}).get("preapproval_id")
    conta = None
    if ref:
        conta = Conta.query.get(ref[0])
    if not conta and assin_id:
        conta = Conta.query.filter_by(mp_assinatura_id=assin_id).first()
    if not conta:
        current_app.logger.warning("Pagamento %s sem conta identificável (ref=%s)", pid, p.get("external_reference"))
        return None

    plano = ref[1] if ref else conta.plano
    ciclo = ref[2] if ref else (conta.ciclo or "mensal")
    metodo = ref[3] if ref else ("recorrente" if assin_id else "avulso")

    c = Cobranca.query.filter_by(mp_pagamento_id=str(pid)).first()
    if not c:
        c = Cobranca(mp_pagamento_id=str(pid), conta_id=conta.id, origem="mercadopago", tipo="assinatura")
        db.session.add(c)
    c.mp_assinatura_id = assin_id or c.mp_assinatura_id
    c.plano, c.ciclo = plano, ciclo
    c.meio = "pix" if p.get("payment_method_id") == "pix" else MEIOS.get(p.get("payment_type_id"), "outro")
    c.valor = float(p.get("transaction_amount") or 0)
    liquido = (p.get("transaction_details") or {}).get("net_received_amount")
    c.valor_liquido = float(liquido) if liquido is not None else None
    c.status = STATUS_PAGAMENTO.get(p.get("status"), p.get("status"))
    c.descricao = p.get("description") or f"{planos.PLANOS[plano]['nome']} ({ciclo})"
    c.pago_em = _data_mp(p.get("date_approved")) or c.pago_em

    if c.status == "aprovado" and not c.aplicado:
        if plano in planos.PAGOS:
            ativar(conta, plano, ciclo, metodo)
            estender_acesso(conta, ciclo)
        c.aplicado = True
    db.session.commit()
    return c


def processar_assinatura(aid):
    a = mp.assinatura(aid)
    if str(a.get("external_reference") or "").startswith("p:"):
        return processar_assinatura_pacote(aid, a)
    ref = ler_referencia(a.get("external_reference"))
    conta = Conta.query.filter_by(mp_assinatura_id=str(aid)).first() or (Conta.query.get(ref[0]) if ref else None)
    if not conta:
        return None
    status = STATUS_ASSINATURA.get(a.get("status"), a.get("status"))
    # Um aviso de uma assinatura antiga não pode derrubar a assinatura nova da mesma conta
    if conta.mp_assinatura_id and conta.mp_assinatura_id != str(aid) and status != "ativa":
        return conta
    conta.mp_assinatura_id = str(aid)
    if status == "ativa" and ref:
        ativar(conta, ref[1], ref[2], "recorrente")
        if not conta.pago_ate or conta.pago_ate < datetime.utcnow():
            # Libera já; o pagamento aprovado (aviso separado) estende o acesso pelo ciclo completo
            conta.pago_ate = datetime.utcnow()
    elif status == "cancelada":
        conta.assinatura_status = "cancelada"
        conta.cancelado_em = conta.cancelado_em or datetime.utcnow()
    elif status in ("pausada", "pendente"):
        conta.assinatura_status = status
    db.session.commit()
    return conta


def processar_pagamento_autorizado(aid):
    """Cobrança recorrente de uma assinatura: aponta para um pagamento comum."""
    ap = mp.pagamento_autorizado(aid)
    pid = (ap.get("payment") or {}).get("id")
    if pid:
        return processar_pagamento(pid)
    if ap.get("preapproval_id") and ap.get("status") in ("recycling", "cancelled"):
        conta = Conta.query.filter_by(mp_assinatura_id=str(ap["preapproval_id"])).first()
        if conta and conta.assinatura_status == "ativa":
            conta.assinatura_status = "inadimplente"  # cartão recusado; o Mercado Pago tenta de novo
            db.session.commit()
    return None


# ---------------------------------------------------------------- serviço de advogado (pagamento avulso)
def processar_servico(pid, p):
    """Pagamento de elaboração/revisão por advogado (external_reference 'r:<id da revisão>')."""
    from models import Peca, Revisao
    try:
        rid = int(str(p["external_reference"]).split(":")[1])
    except (IndexError, ValueError):
        return None
    r = Revisao.query.get(rid)
    if not r:
        current_app.logger.warning("Pagamento %s de serviço sem pedido (%s)", pid, p.get("external_reference"))
        return None
    c = Cobranca.query.filter_by(mp_pagamento_id=str(pid)).first()
    if not c:
        c = Cobranca(mp_pagamento_id=str(pid), conta_id=r.conta_id, origem="mercadopago", tipo="servico")
        db.session.add(c)
    peca = Peca.query.get(r.peca_id)
    c.meio = "pix" if p.get("payment_method_id") == "pix" else MEIOS.get(p.get("payment_type_id"), "outro")
    c.valor = float(p.get("transaction_amount") or 0)
    liquido = (p.get("transaction_details") or {}).get("net_received_amount")
    c.valor_liquido = float(liquido) if liquido is not None else None
    c.status = STATUS_PAGAMENTO.get(p.get("status"), p.get("status"))
    c.descricao = f"{'Elaboração' if r.servico == 'elaboracao' else 'Revisão'} por advogado — {peca.titulo if peca else ''}"[:300]
    c.pago_em = _data_mp(p.get("date_approved")) or c.pago_em
    if c.status == "aprovado" and not c.aplicado:
        r.pago_em = c.pago_em or datetime.utcnow()
        if r.status == "aguardando_pagamento":
            r.status = "pendente"
        if peca and r.servico != "elaboracao":
            peca.status = "revisao_solicitada"
        c.aplicado = True
        _avisar_admin(r, peca)
    db.session.commit()
    return c


def _avisar_admin(r, peca):
    """E-mail para o administrador quando um serviço é pago (melhor esforço)."""
    try:
        from services import email
        for adm in current_app.config["ADMIN_EMAILS"]:
            tipo = "Elaboração" if r.servico == "elaboracao" else "Revisão"
            email.enviar(adm, f"Novo pedido pago: {tipo} — {peca.titulo if peca else ''}",
                         f"{tipo} por advogado paga (R$ {r.valor or 0:.2f}). Prazo desejado: {r.prazo_desejado or 'não informado'}."
                         f"\nObservações: {r.observacoes or '-'}\nVeja em Administração > Revisões.",
                         f"<p><b>{tipo} por advogado paga</b> (R$ {r.valor or 0:.2f}).</p><p>{html_esc(peca.titulo if peca else '')}</p>"
                         f"<p>Prazo desejado: {r.prazo_desejado or 'não informado'}</p><p>Veja em Administração &gt; Revisões.</p>")
    except Exception:
        current_app.logger.warning("Aviso de pedido pago não enviado", exc_info=True)


def html_esc(t):
    import html
    return html.escape(t or "")


# ---------------------------------------------------------------- pacotes extras de contratos
def _ref_pacote(ref):
    """'p:12:2:avulso' -> (12, 2, 'avulso')"""
    try:
        _, cid, qtd, metodo = str(ref).split(":")
        return int(cid), max(1, int(qtd)), metodo
    except ValueError:
        return None


def processar_pacote(pid, p, sub=None):
    ref = _ref_pacote(p.get("external_reference"))
    conta = Conta.query.get(ref[0]) if ref else Conta.query.filter_by(pacotes_mp_assinatura_id=sub).first()
    if not conta:
        return None
    qtd = ref[1] if ref else (conta.pacotes_contratos or 1)
    metodo = ref[2] if ref else "recorrente"
    c = Cobranca.query.filter_by(mp_pagamento_id=str(pid)).first()
    if not c:
        c = Cobranca(mp_pagamento_id=str(pid), conta_id=conta.id, origem="mercadopago", tipo="assinatura")
        db.session.add(c)
    c.mp_assinatura_id = sub or c.mp_assinatura_id
    c.plano, c.ciclo = "pacote_contratos", "mensal"
    c.meio = "pix" if p.get("payment_method_id") == "pix" else MEIOS.get(p.get("payment_type_id"), "outro")
    c.valor = float(p.get("transaction_amount") or 0)
    liquido = (p.get("transaction_details") or {}).get("net_received_amount")
    c.valor_liquido = float(liquido) if liquido is not None else None
    c.status = STATUS_PAGAMENTO.get(p.get("status"), p.get("status"))
    c.descricao = f"{qtd} pacote(s) de +10 contratos (mensal)"
    c.pago_em = _data_mp(p.get("date_approved")) or c.pago_em
    if c.status == "aprovado" and not c.aplicado:
        agora = datetime.utcnow()
        base = conta.pacotes_ate if conta.pacotes_ate and conta.pacotes_ate > agora else agora
        conta.pacotes_ate = somar_meses(base, 1)
        conta.pacotes_contratos = qtd
        conta.pacotes_metodo = metodo
        conta.pacotes_status = "ativa"
        c.aplicado = True
    db.session.commit()
    return c


def processar_assinatura_pacote(aid, a):
    ref = _ref_pacote(a.get("external_reference"))
    conta = Conta.query.filter_by(pacotes_mp_assinatura_id=str(aid)).first() or (Conta.query.get(ref[0]) if ref else None)
    if not conta:
        return None
    status = STATUS_ASSINATURA.get(a.get("status"), a.get("status"))
    if conta.pacotes_mp_assinatura_id and conta.pacotes_mp_assinatura_id != str(aid) and status != "ativa":
        return conta
    conta.pacotes_mp_assinatura_id = str(aid)
    if status == "ativa" and ref:
        conta.pacotes_contratos, conta.pacotes_metodo, conta.pacotes_status = ref[1], "recorrente", "ativa"
        if not conta.pacotes_ate or conta.pacotes_ate < datetime.utcnow():
            conta.pacotes_ate = datetime.utcnow()  # libera já; o pagamento aprovado estende 1 mês
    elif status in ("cancelada", "pausada", "pendente"):
        conta.pacotes_status = status
    db.session.commit()
    return conta
