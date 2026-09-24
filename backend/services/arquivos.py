"""Upload seguro e extração de texto de PDFs (com marcação de página para a IA citar)."""
import io
import os
import uuid

from flask import current_app
from pypdf import PdfReader
from werkzeug.utils import secure_filename

from extensions import ErroAPI

EXTENSOES = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".txt"}


def salvar(arquivo, subpasta):
    nome = secure_filename(arquivo.filename or "arquivo")
    ext = os.path.splitext(nome)[1].lower()
    if ext not in EXTENSOES:
        raise ErroAPI("Formato não aceito. Envie PDF, imagem, DOC/DOCX ou TXT.")
    pasta = os.path.join(current_app.config["UPLOAD_DIR"], subpasta)
    os.makedirs(pasta, exist_ok=True)
    caminho_rel = os.path.join(subpasta, f"{uuid.uuid4().hex}{ext}")
    arquivo.save(os.path.join(current_app.config["UPLOAD_DIR"], caminho_rel))
    return caminho_rel, nome


def caminho_absoluto(rel):
    return os.path.join(current_app.config["UPLOAD_DIR"], rel)


def texto_de_pdf_bytes(conteudo):
    leitor = PdfReader(io.BytesIO(conteudo))
    partes = []
    for i, pagina in enumerate(leitor.pages, start=1):
        try:
            t = pagina.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            partes.append(f"[pág. {i}]\n{t.strip()}")
    return "\n\n".join(partes)


def extrair_texto(caminho_rel):
    caminho = caminho_absoluto(caminho_rel)
    ext = os.path.splitext(caminho)[1].lower()
    with open(caminho, "rb") as f:
        conteudo = f.read()
    if ext == ".pdf":
        texto = texto_de_pdf_bytes(conteudo)
        if len(texto.strip()) < 200:
            raise ErroAPI("Este PDF parece ser uma imagem escaneada, sem texto selecionável. "
                          "Envie uma versão pesquisável (com OCR).")
        return texto
    if ext == ".txt":
        return conteudo.decode("utf-8", errors="ignore")
    if ext == ".docx":
        import zipfile, re
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n"))
    raise ErroAPI("Para análise, envie o documento em PDF, DOCX ou TXT.")


def cortar(texto, limite=None):
    limite = limite or current_app.config["MAX_CHARS_DOCUMENTO"]
    if len(texto) <= limite:
        return texto
    metade = limite // 2
    return texto[:metade] + "\n\n[... trecho intermediário omitido por limite de tamanho ...]\n\n" + texto[-metade:]
