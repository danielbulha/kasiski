"""Tabelas de preços de referência: importação de planilhas (CSV/XLSX) e busca por palavras (RAG estruturado).

As planilhas oficiais têm formatos variados (SINAPI começa com linhas de título, CMED tem dezenas de
colunas...). Por isso a importação é em dois passos: `ler_previa` acha a linha de cabeçalho e sugere
quais colunas são código/descrição/unidade/preço; o admin confirma e `importar` grava os itens.
"""
import csv
import io
import re
import unicodedata

from extensions import ErroAPI, db
from models import ItemReferencia, TabelaReferencia

FONTES = {"sinapi": "SINAPI (Caixa/IBGE)", "sicro": "SICRO (DNIT)", "cmed": "CMED (ANVISA) — medicamentos",
          "sigtap": "SIGTAP (SUS)", "cct": "Convenção coletiva (pisos salariais)", "bps": "Banco de Preços em Saúde",
          "outra": "Outra tabela"}
_STOP = set("para pela pelo com sem das dos uma umas uns por que tipo inclusive exceto conforme".split())


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def termos(consulta):
    return [w for w in re.findall(r"[a-z0-9]{3,}", norm(consulta)) if w not in _STOP][:8]


def para_preco(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s or s in "-.,":
        return None
    if "," in s and "." in s:          # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                      # 1234,56
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- leitura
def _linhas(conteudo, nome):
    nome = (nome or "").lower()
    if nome.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
        except Exception:
            raise ErroAPI("Não foi possível abrir a planilha. Salve como .xlsx ou .csv e tente de novo.")
        ws = max(wb.worksheets, key=lambda w: w.max_row or 0)  # a aba com mais linhas
        for row in ws.iter_rows(values_only=True):
            yield ["" if c is None else c for c in row]
        return
    if nome.endswith(".xls"):
        raise ErroAPI("Formato .xls antigo não é aceito. Abra no Excel e salve como .xlsx ou .csv.")
    texto = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    amostra = texto[:5000]
    sep = max((";", ",", "\t", "|"), key=amostra.count)
    for row in csv.reader(io.StringIO(texto), delimiter=sep):
        yield row


# pontuação por coluna: (prefixos fortes, palavras que ajudam, palavras que descartam)
_PISTAS = {
    "codigo": (("codigo", "cod", "catmat", "catser", "ggrem", "registro", "sigtap"), ("item",), ("descri", "preco", "valor")),
    "descricao": (("descri", "denomina", "produto", "cargo", "funcao", "categoria", "insumo", "procedimento", "material",
                   "servico", "apresenta", "nome", "item"), ("insumo", "composicao"), ("codigo", "cod ", "unid", "preco", "valor")),
    "unidade": (("unid", "und", "un ", "un.", "un"), ("medida",), ("preco", "valor", "descri")),
    "preco": (("preco", "custo", "valor", "pmvg", "pf ", "piso", "salario", "mediana", "total"),
              ("r$", "mediano", "unitario", "sem impostos", "desonerado"), ("origem", "data", "codigo", "%", "aliquota")),
}


def _sugerir(cabecalho):
    cab = [norm(c) for c in cabecalho]
    sug, usados = {}, set()
    for campo in ("descricao", "preco", "codigo", "unidade"):
        fortes, ajudam, descartam = _PISTAS[campo]
        melhor, idx = 0, None
        for i, c in enumerate(cab):
            if i in usados or not c or any(d in c for d in descartam):
                continue
            pontos = (3 if c.startswith(fortes) else 0) + (1 if any(f" {f}" in f" {c}" for f in fortes) else 0) \
                + sum(1 for a in ajudam if a in c)
            if campo == "unidade" and c in ("un", "und", "unid", "unidade"):
                pontos += 3
            if pontos > melhor:
                melhor, idx = pontos, i
        if idx is not None:
            sug[campo] = idx
            usados.add(idx)
    return sug


def ler_previa(conteudo, nome):
    linhas = []
    for i, row in enumerate(_linhas(conteudo, nome)):
        linhas.append([str(c).strip() if not isinstance(c, (int, float)) else c for c in row])
        if i >= 60:
            break
    if not linhas:
        raise ErroAPI("A planilha está vazia.")
    # cabeçalho = primeira linha com 3+ células de texto que mencione descrição/produto
    idx = 0
    for i, row in enumerate(linhas[:40]):
        textos = [norm(c) for c in row if isinstance(c, str) and c.strip()]
        if len(textos) >= 3 and any(t.startswith(("descri", "denomina", "produto", "servico", "item")) for t in textos):
            idx = i
            break
    cab = [str(c) for c in linhas[idx]]
    return {"linha_cabecalho": idx, "colunas": cab, "sugestao": _sugerir(cab),
            "exemplos": [[str(c) for c in r] for r in linhas[idx + 1: idx + 6]]}


def importar(tabela, conteudo, nome, mapa, linha_cabecalho):
    """mapa: {'codigo': i, 'descricao': i, 'unidade': i, 'preco': i} (índices de coluna)."""
    if mapa.get("descricao") is None or mapa.get("preco") is None:
        raise ErroAPI("Indique pelo menos as colunas de descrição e de preço.")
    ItemReferencia.query.filter_by(tabela_id=tabela.id).delete()
    n, lote = 0, []

    def col(row, campo):
        i = mapa.get(campo)
        return row[i] if i is not None and i < len(row) else None

    for i, row in enumerate(_linhas(conteudo, nome)):
        if i <= linha_cabecalho:
            continue
        desc = str(col(row, "descricao") or "").strip()
        preco = para_preco(col(row, "preco"))
        if len(desc) < 3 or preco is None or preco <= 0:
            continue
        codigo = col(row, "codigo")
        codigo = (str(int(codigo)) if isinstance(codigo, float) and codigo.is_integer() else str(codigo or "")).strip()[:60]
        lote.append({"tabela_id": tabela.id, "codigo": codigo or None, "descricao": desc[:2000],
                     "unidade": str(col(row, "unidade") or "").strip()[:40] or None, "preco": preco,
                     "termos": norm(f"{codigo} {desc}")})
        n += 1
        if len(lote) >= 2000:
            db.session.bulk_insert_mappings(ItemReferencia, lote)
            lote = []
        if n >= 200000:
            break
    if lote:
        db.session.bulk_insert_mappings(ItemReferencia, lote)
    if not n:
        raise ErroAPI("Nenhuma linha com descrição e preço válido foi encontrada. Confira as colunas escolhidas.")
    tabela.n_itens = n
    db.session.commit()
    return n


# ---------------------------------------------------------------- busca
def buscar(consulta, uf=None, fontes=None, limite=15):
    """Itens das tabelas ativas que contêm todos os termos (ou, se nada, a maioria deles)."""
    ts = termos(consulta)
    if not ts:
        return []
    tabelas = {t.id: t for t in TabelaReferencia.query.filter_by(ativa=True).all()
               if (not uf or not t.uf or t.uf == uf) and (not fontes or t.fonte in fontes)}
    if not tabelas:
        return []
    base = ItemReferencia.query.filter(ItemReferencia.tabela_id.in_(list(tabelas)))
    q = base
    for t in ts:
        q = q.filter(ItemReferencia.termos.like(f"%{t}%"))
    achados = q.limit(limite * 3).all()
    if len(achados) < 3 and len(ts) > 2:  # afrouxa: basta metade dos termos, ordena por quantos batem
        q = base.filter(db.or_(*[ItemReferencia.termos.like(f"%{t}%") for t in ts])).limit(600)
        achados = sorted(q.all(), key=lambda it: -sum(t in (it.termos or "") for t in ts))
        achados = [a for a in achados if sum(t in (a.termos or "") for t in ts) >= max(2, len(ts) // 2)]
    achados.sort(key=lambda it: (-sum(t in (it.termos or "") for t in ts), len(it.descricao or "")))
    return [a.to_dict(tabelas[a.tabela_id]) for a in achados[:limite]]


def contexto_para_ia(itens_proposta, uf=None, por_item=3):
    """Texto com as referências mais próximas de cada item, para a IA citar na análise."""
    blocos = []
    for it in itens_proposta[:30]:
        refs = buscar(it.get("descricao", ""), uf=uf, limite=por_item)
        if refs:
            linhas = "; ".join(f"{r['tabela']} cód. {r.get('codigo') or '—'} \"{r['descricao'][:120]}\" "
                               f"{r.get('unidade') or ''} R$ {r['preco']:.2f}" for r in refs)
            blocos.append(f"- {it.get('descricao', '')[:120]}: {linhas}")
    return "\n".join(blocos)
