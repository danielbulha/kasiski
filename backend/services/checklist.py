"""Checklist de habilitação (catálogo em backend/data/checklist_habilitacao.json) e importação para o Cofre."""
import json
import os
import re
from datetime import date, datetime
from functools import lru_cache

from extensions import db
from models import Documento

ARQUIVO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "checklist_habilitacao.json")


@lru_cache(maxsize=1)
def definicao():
    with open(ARQUIVO, encoding="utf-8") as f:
        return json.load(f)


def itens_para(segmentos=None):
    """Itens gerais + os do(s) segmento(s)."""
    seg = set(segmentos or [])
    return [i for i in definicao()["itens"] if not i.get("segmentos") or seg & set(i["segmentos"])]


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def _data(v):
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def importar(empresa, selecao):
    """selecao = [{id, tem, validade}] ou lista de ids. Cria um Documento por item que ainda não existe no cofre
    (compara pelo item do catálogo e pelo nome). Itens que a empresa não tem entram como pendentes."""
    catalogo = {i["id"]: i for i in definicao()["itens"]}
    existentes = Documento.query.filter_by(empresa_id=empresa.id).all()
    ja_ids = {x.checklist_id for x in existentes if x.checklist_id}
    ja_nomes = {_norm(x.tipo) for x in existentes}
    criados = []
    for s in selecao or []:
        s = s if isinstance(s, dict) else {"id": s}
        item = catalogo.get(str(s.get("id")))
        if not item or item["id"] in ja_ids or _norm(item["tipo"]) in ja_nomes:
            continue
        tem = bool(s.get("tem"))
        validade = _data(s.get("validade")) if item.get("tem_validade") else None
        doc = Documento(empresa_id=empresa.id, categoria=item["categoria"], tipo=item["tipo"][:120],
                        descricao=f"{item['onde']} · validade: {item['validade']} · {item['base']}"[:500],
                        validade=validade, pendente=not tem and not validade, checklist_id=item["id"])
        db.session.add(doc)
        criados.append(doc)
        ja_ids.add(item["id"])
    db.session.flush()
    return criados


def importar_publicos(conta, usuario, empresa):
    """No cadastro da 1ª empresa: traz os checklists montados no site com o mesmo e-mail."""
    from models import ChecklistPublico
    feitos = 0
    for c in ChecklistPublico.query.filter(ChecklistPublico.email == (usuario.email or "").lower(), ChecklistPublico.conta_id.is_(None)) \
            .order_by(ChecklistPublico.criado_em.desc()).limit(2):
        feitos += len(importar(empresa, c.itens))
        c.conta_id, c.importado_em = conta.id, datetime.utcnow()
    return feitos
