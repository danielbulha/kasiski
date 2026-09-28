"""Tabelas de preços de referência: importação de planilhas (CSV/XLSX) e busca por palavras (RAG estruturado).

As planilhas oficiais têm formatos variados (SINAPI começa com linhas de título, CMED tem dezenas de
colunas...). Por isso a importação é em dois passos: `ler_previa` acha a linha de cabeçalho e sugere
quais colunas são código/descrição/unidade/preço; o admin confirma e `importar` grava os itens.
"""
import csv
import io
import re
import unicodedata
from datetime import date

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
        if i >= 100:
            break
    if not linhas:
        raise ErroAPI("A planilha está vazia.")
    # cabeçalho = primeira linha com 3+ células de texto que mencione descrição/produto
    idx = 0
    for i, row in enumerate(linhas[:90]):
        textos = [norm(c) for c in row if isinstance(c, str) and c.strip()]
        if len(textos) >= 3 and any(t.startswith(("descri", "denomina", "produto", "servico", "item", "substancia", "cargo", "funcao"))
                                    for t in textos):
            idx = i
            break
    cab = [str(c) for c in linhas[idx]]
    perfil = detectar_perfil(cab)
    sug = _sugerir(cab)
    if perfil == "cmed":
        sug.update({k: v for k, v in _mapa_cmed(cab).items() if v is not None})
    precos_idx = [i for i, c in enumerate(cab) if _eh_coluna_preco(c)]
    return {"linha_cabecalho": idx, "colunas": cab, "sugestao": sug, "perfil": perfil, "colunas_preco": precos_idx,
            "exemplos": [[str(c) for c in r] for r in linhas[idx + 1: idx + 6]]}


def importar(tabela, conteudo, nome, mapa, linha_cabecalho):
    """mapa: {'codigo': i, 'descricao': i, 'unidade': i, 'preco': i, 'apresentacao': i} (índices de coluna).
    Todas as outras colunas são guardadas: as de preço em `precos` (ex.: CMED PF/PMVG por alíquota de ICMS) e as
    informativas em `extras` (laboratório, registro, CAP, tarja, origem do preço...)."""
    if mapa.get("descricao") is None or mapa.get("preco") is None:
        raise ErroAPI("Indique pelo menos as colunas de descrição e de preço.")
    ItemReferencia.query.filter_by(tabela_id=tabela.id).delete()
    n, lote = 0, []
    cab, perfil, idx_preco, idx_info, idx_busca = [], None, [], [], []

    def col(row, campo):
        i = mapa.get(campo)
        return row[i] if i is not None and i < len(row) else None

    usados = {v for k, v in mapa.items() if v is not None and k != "preco"}
    for i, row in enumerate(_linhas(conteudo, nome)):
        if i < linha_cabecalho:
            continue
        if i == linha_cabecalho:
            cab = [str(c or "").strip() for c in row]
            perfil = detectar_perfil(cab) or tabela.fonte
            idx_preco = [j for j, c in enumerate(cab) if c and (_eh_coluna_preco(c) or j == mapa.get("preco"))]
            idx_info = [j for j, c in enumerate(cab) if c and j not in usados and j not in idx_preco][:60]
            idx_busca = [j for j in idx_info if norm(cab[j]).startswith(_COLUNAS_BUSCA)]
            tabela.colunas = ([{"nome": cab[j], "tipo": "preco"} for j in idx_preco] +
                              [{"nome": cab[j], "tipo": "info"} for j in idx_info])
            continue
        desc = str(col(row, "descricao") or "").strip()
        if mapa.get("apresentacao") is not None:
            ap = str(col(row, "apresentacao") or "").strip()
            desc = f"{desc} — {ap}" if ap and ap not in desc else desc
        preco = para_preco(col(row, "preco"))
        if len(desc) < 3 or preco is None or preco <= 0:
            continue
        codigo = col(row, "codigo")
        codigo = (str(int(codigo)) if isinstance(codigo, float) and codigo.is_integer() else str(codigo or "")).strip()[:60]
        precos, extras = {}, {}
        for j in idx_preco:
            v = para_preco(row[j]) if j < len(row) else None
            if v is not None and v > 0:
                precos[cab[j]] = round(v, 4)
        for j in idx_info:
            v = row[j] if j < len(row) else None
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            v = str(v if v is not None else "").strip()
            if v and v not in ("-", "--"):
                extras[cab[j]] = v[:250]
        busca_extra = " ".join(extras.get(cab[j], "") for j in idx_busca)
        lote.append({"tabela_id": tabela.id, "codigo": codigo or None, "descricao": desc[:2000],
                     "unidade": str(col(row, "unidade") or "").strip()[:40] or None, "preco": preco,
                     "precos": precos or None, "extras": extras or None,
                     "termos": norm(f"{codigo} {desc} {busca_extra}")})
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
    if perfil and tabela.fonte == "outra" and perfil in FONTES:
        tabela.fonte = perfil
    db.session.commit()
    return n


# ---------------------------------------------------------------- perfis de tabela (colunas conhecidas)
_COLUNAS_BUSCA = ("substancia", "principio", "laboratorio", "fabricante", "marca", "classe terapeutica", "apresentacao",
                  "produto", "grupo", "classe", "cbo", "registro", "ean")


def _eh_coluna_preco(nome):
    c = norm(nome)
    if not c:
        return False
    if c.startswith(("pf ", "pmvg", "pmc ")) or c in ("pf", "pmvg", "pmc"):
        return True
    if any(x in c for x in ("data", "origem", "codigo", "aliquota", "coeficiente", "lista de concessao", "regime")):
        return False
    return c.startswith(("preco", "custo", "valor", "piso", "salario", "mediana")) or c == "total"


def detectar_perfil(cabecalho):
    cab = " | ".join(norm(c) for c in cabecalho)
    if "pmvg" in cab or "ggrem" in cab:
        return "cmed"
    if "sicro" in cab:
        return "sicro"
    if "sinapi" in cab or ("composicao" in cab and "custo" in cab) or "origem de preco" in cab or "preco mediano" in cab:
        return "sinapi"
    if "sigtap" in cab or ("procedimento" in cab and "valor s" in cab):
        return "sigtap"
    if "piso" in cab or ("cbo" in cab and ("salario" in cab or "funcao" in cab)):
        return "cct"
    return None


def _mapa_cmed(cab):
    c = [norm(x) for x in cab]

    def achar(*prefixos):
        for p in prefixos:
            for i, x in enumerate(c):
                if x.startswith(p):
                    return i
        return None
    return {"codigo": achar("codigo ggrem", "ggrem"), "descricao": achar("produto"), "apresentacao": achar("apresentacao"),
            "preco": achar("pmvg sem impostos", "pf sem impostos", "pf 0%")}


# Alíquota interna (modal) do ICMS em 2026, com o adicional de fundo de pobreza quando cobrado junto (RJ, AL, SE).
# Serve de sugestão para escolher a coluna da CMED; o usuário ajusta na proposta (ex.: genéricos em SP = 12%).
ICMS_UF = {"AC": 19, "AL": 20, "AP": 18, "AM": 20, "BA": 20.5, "CE": 20, "DF": 20, "ES": 17, "GO": 19, "MA": 23,
           "MT": 17, "MS": 17, "MG": 18, "PA": 19, "PB": 20, "PR": 19.5, "PE": 20.5, "PI": 22.5, "RJ": 22, "RN": 20,
           "RS": 17, "RO": 19.5, "RR": 20, "SC": 17, "SP": 18, "SE": 20, "TO": 20}


def _sim(v):
    return norm(v) in ("sim", "s", "yes", "x", "true", "1")


def extra(item, *prefixos):
    for k, v in (item.get("extras") or {}).items():
        if norm(k).startswith(prefixos):
            return v
    return None


def _coluna(precos, base, aliq):
    """Acha a coluna 'PF 17,5%' / 'PMVG 18 %' / 'PF Sem Impostos' em `precos` (tolerante a espaço e vírgula)."""
    alvo = norm(f"{base} {aliq}").replace(" ", "").replace(",", ".").rstrip("%")
    for k, v in precos.items():
        kk = norm(k).replace(" ", "").replace(",", ".")
        if "alc" in kk:
            continue  # colunas de Área de Livre Comércio só valem para a ALC
        if kk.rstrip("%") == alvo:
            return k, v
    return None, None


def preco_aplicavel(item, fonte=None, uf=None, icms=None, criterio=None):
    """Preço de referência que vale para a compra pública e a regra usada.
    CMED: o teto é o PMVG quando o produto tem CAP ou o edital manda usar o PMVG; senão, o PF. A coluna é a da
    alíquota de ICMS do estado do órgão (0% quando o produto é isento pelo Convênio CONFAZ 87/2002)."""
    fonte = fonte or item.get("fonte")
    precos = item.get("precos") or {}
    if fonte == "cmed" and precos:
        cap = _sim(extra(item, "cap"))
        isento = _sim(extra(item, "confaz")) or _sim(extra(item, "icms 0"))
        crit = (criterio or "").upper()
        base = crit if crit in ("PMVG", "PF") else ("PMVG" if cap else "PF")
        if icms is None and uf:
            icms = ICMS_UF.get(uf.upper())
        aliq = 0 if isento else icms
        tentativas = [f"{aliq:g}".replace(".", ",") + "%"] if aliq is not None else []
        tentativas.append("sem impostos")
        for a in tentativas:
            k, v = _coluna(precos, base, a)
            if v:
                motivos = [f"{base} com ICMS {a}" if a != "sem impostos" else
                           f"{base} sem impostos ({'informe a UF do órgão para aplicar o ICMS' if aliq is None else 'coluna da alíquota não encontrada'})"]
                if isento:
                    motivos.append("isento de ICMS (Convênio CONFAZ 87/2002)")
                if base == "PMVG" and cap and crit != "PMVG":
                    motivos.append("produto sujeito ao CAP: o teto em compras públicas é o PMVG")
                return {"valor": v, "coluna": k, "regra": "; ".join(motivos), "teto": True, "cap": cap}
    return {"valor": item.get("preco"), "coluna": None, "regra": None, "teto": fonte in ("cmed", "bps"), "cap": False}


# ---------------------------------------------------------------- busca
def _tabelas_ativas(uf=None, fontes=None, desonerado=None):
    """Tabelas ativas que servem ao filtro; da mesma fonte/UF/regime fica só a data-base mais recente."""
    tabs = []
    for t in TabelaReferencia.query.filter_by(ativa=True).all():
        if uf and t.uf and t.uf != uf:
            continue
        if fontes and t.fonte not in fontes:
            continue
        if desonerado is not None and t.desonerado is not None and t.desonerado != desonerado:
            continue
        tabs.append(t)
    melhor = {}
    for t in tabs:
        chave = (t.fonte, t.uf, t.desonerado, t.fonte == "outra" and t.id)
        if chave not in melhor or (t.data_base or date.min) > (melhor[chave].data_base or date.min):
            melhor[chave] = t
    return {t.id: t for t in melhor.values()}


def por_codigo(codigo, uf=None, fontes=None, desonerado=None):
    """Itens com o código exato (SINAPI 94990, GGREM, registro ANVISA, EAN) nas tabelas ativas."""
    cod = re.sub(r"[\s.\-/]", "", str(codigo or ""))
    if len(cod) < 3:
        return []
    tabelas = _tabelas_ativas(uf, fontes, desonerado)
    if not tabelas:
        return []
    base = ItemReferencia.query.filter(ItemReferencia.tabela_id.in_(list(tabelas)))
    achados = base.filter(ItemReferencia.codigo.in_({cod, str(codigo).strip()})).limit(10).all()
    if not achados and len(cod) >= 9:  # registro ANVISA / EAN estão nas colunas informativas (entram no texto de busca)
        achados = base.filter(ItemReferencia.termos.like(f"%{cod}%")).limit(10).all()
    return [{**a.to_dict(tabelas[a.tabela_id]), "aderencia": 1.0, "por_codigo": True} for a in achados]


def buscar(consulta, uf=None, fontes=None, limite=15, desonerado=None):
    """Itens das tabelas ativas que contêm todos os termos (ou, se nada, a maioria deles)."""
    ts = termos(consulta)
    if not ts:
        return []
    tabelas = _tabelas_ativas(uf, fontes, desonerado)
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
    saida = []
    for a in achados[:limite]:
        d = a.to_dict(tabelas[a.tabela_id])
        d["aderencia"] = round(sum(t in (a.termos or "") for t in ts) / len(ts), 2)
        saida.append(d)
    return saida


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
