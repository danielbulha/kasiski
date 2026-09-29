"""Arquivo da licitação: quando a licitação termina (perdida, desistência ou contrato ativo), todos os seus
documentos ficam reunidos em um dossiê no Arquivo — edital, anexos, atas, análises, peças, propostas e contrato."""
import io
import json
import os
import re
import zipfile
from datetime import datetime, timedelta

from flask import current_app

from extensions import db
from models import Analise, AnaliseConcorrente, Contrato, DocumentoLicitacao, Edital, Movimento, Peca, Prazo, Proposta

FINAIS = {"perdida", "desistencia", "contrato_ativo"}
DIAS_NO_QUADRO = 15


def fora_do_quadro(ed):
    return bool(ed.arquivado_em and ed.arquivado_em < datetime.utcnow() - timedelta(days=DIAS_NO_QUADRO))


def arquivar_encerradas():
    """Editais que chegaram a uma etapa final antes desta regra existir."""
    n = 0
    for ed in Edital.query.filter(Edital.etapa.in_(FINAIS), Edital.arquivado_em.is_(None)):
        ed.arquivado_em = ed.etapa_em or datetime.utcnow()
        n += 1
    db.session.commit()
    return n


def conteudo(ed):
    """Tudo o que pertence à licitação, para o dossiê."""
    return {
        "documentos": DocumentoLicitacao.query.filter_by(edital_id=ed.id).order_by(DocumentoLicitacao.criado_em).all(),
        "analises": Analise.query.filter_by(edital_id=ed.id, status="concluida").order_by(Analise.id.desc()).all(),
        "analises_concorrentes": AnaliseConcorrente.query.filter_by(edital_id=ed.id).all(),
        "pecas": Peca.query.filter_by(edital_id=ed.id).order_by(Peca.id).all(),
        "propostas": Proposta.query.filter_by(edital_id=ed.id).order_by(Proposta.id).all(),
        "contratos": Contrato.query.filter_by(edital_id=ed.id).all(),
        "prazos": Prazo.query.filter_by(edital_id=ed.id).order_by(Prazo.data).all(),
        "movimentos": Movimento.query.filter_by(edital_id=ed.id).order_by(Movimento.criado_em).all(),
    }


def resumo(ed):
    c = conteudo(ed)
    return {"edital": ed.to_dict(), "documentos": [d.to_dict() for d in c["documentos"]],
            "pecas": [{"id": p.id, "titulo": p.titulo, "tipo": p.tipo, "criado_em": p.criado_em.isoformat() if p.criado_em else None} for p in c["pecas"]],
            "propostas": [{"id": p.id, "titulo": getattr(p, "titulo", None) or f"Proposta {p.id}"} for p in c["propostas"]],
            "contratos": [{"id": k.id, "numero": k.numero, "valor": k.valor, "tem_arquivo": bool(k.arquivo)} for k in c["contratos"]],
            "analises": len(c["analises"]), "analises_concorrentes": len(c["analises_concorrentes"]),
            "prazos": len(c["prazos"]), "movimentos": [{"de": m.de, "para": m.para, "motivo": m.motivo, "autor": m.autor,
                                                        "criado_em": m.criado_em.isoformat() if m.criado_em else None} for m in c["movimentos"]]}


def _nome(texto, ext=""):
    base = re.sub(r"[^\w\-. ]+", "", texto or "arquivo", flags=re.UNICODE).strip()[:80] or "arquivo"
    return base + ext if ext and not base.lower().endswith(ext) else base


def _add_arquivo(z, rel, destino):
    if not rel:
        return False
    caminho = os.path.join(current_app.config["UPLOAD_DIR"], rel)
    if os.path.exists(caminho):
        z.write(caminho, destino)
        return True
    return False


def zip_dossie(ed):
    """ZIP com a pasta completa da licitação."""
    c = conteudo(ed)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        linhas = [f"Licitação: {ed.numero or ed.numero_controle or ed.id}", f"Órgão: {ed.orgao or ''}", f"Objeto: {ed.objeto or ''}",
                  f"Valor estimado: {ed.valor_estimado or ''}", f"Sessão: {ed.data_abertura or ''}", f"Etapa final: {ed.etapa or ''}",
                  f"Motivo de saída: {ed.motivo_saida or ''}", f"Link PNCP: {ed.link or ''}", "", "Movimentações:"]
        linhas += [f"- {m.criado_em:%d/%m/%Y %H:%M} {m.de or ''} -> {m.para} {('— ' + m.motivo) if m.motivo else ''}" for m in c["movimentos"] if m.criado_em]
        linhas += ["", "Prazos:"] + [f"- {p.data:%d/%m/%Y %H:%M} {p.titulo}{' (concluído)' if p.concluido else ''}" for p in c["prazos"] if p.data]
        z.writestr("00-resumo.txt", "\n".join(linhas))
        _add_arquivo(z, ed.arquivo, "01-edital/" + _nome(ed.nome_arquivo or "edital.pdf"))
        for i, d in enumerate(c["documentos"], 1):
            if not _add_arquivo(z, d.arquivo, f"02-documentos/{i:02d}-{d.tipo}-{_nome(d.nome_arquivo or d.titulo)}"):
                if d.texto:
                    z.writestr(f"02-documentos/{i:02d}-{d.tipo}-{_nome(d.titulo, '.txt')}", d.texto)
            if d.analise:
                z.writestr(f"02-documentos/{i:02d}-{d.tipo}-analise.json", json.dumps(d.analise, ensure_ascii=False, indent=2))
        for a in c["analises"][:1]:
            z.writestr("03-analise-do-edital.json", json.dumps(a.resultado or {}, ensure_ascii=False, indent=2))
        for a in c["analises_concorrentes"]:
            z.writestr(f"04-concorrentes/analise-{a.id}-{a.tipo}.json", json.dumps(a.resultado or {}, ensure_ascii=False, indent=2))
        for p in c["pecas"]:
            z.writestr(f"05-pecas/{p.id:04d}-{_nome(p.titulo, '.txt')}", p.conteudo or "")
        for p in c["propostas"]:
            z.writestr(f"06-propostas/proposta-{p.id}.json", json.dumps(p.to_dict() if hasattr(p, "to_dict") else {}, ensure_ascii=False, indent=2, default=str))
        for k in c["contratos"]:
            _add_arquivo(z, k.arquivo, f"07-contrato/{_nome(k.nome_arquivo or f'contrato-{k.numero or k.id}.pdf')}")
    buf.seek(0)
    return buf
