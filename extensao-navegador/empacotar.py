"""Gera o .zip para enviar à Chrome Web Store (e à loja do Edge): python3 empacotar.py

Tira do manifest os endereços de teste local (127.0.0.1) e confere se config.js aponta para a API de produção.
O arquivo sai em dist/kasiski-sala-de-disputa-<versão>.zip.
"""
import json
import os
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQUIVOS = ["background.js", "comum.js", "config.js", "observador.js", "ponte-kasiski.js", "popup.html", "popup.js",
            "adaptadores/comprasgov.js", "icones/icone-16.png", "icones/icone-32.png", "icones/icone-48.png",
            "icones/icone-128.png"]


def sem_local(lista):
    return [x for x in lista if "127.0.0.1" not in x and "localhost" not in x]


def main():
    m = json.load(open(os.path.join(AQUI, "manifest.json"), encoding="utf-8"))
    m["host_permissions"] = sem_local(m.get("host_permissions", []))
    for cs in m.get("content_scripts", []):
        cs["matches"] = sem_local(cs["matches"])
    config = open(os.path.join(AQUI, "config.js"), encoding="utf-8").read()
    if "certame-api-va8f.onrender.com" not in config or "127.0.0.1" in config.split("const KASISKI_API")[1].split(";")[0]:
        raise SystemExit("config.js não aponta para a API de produção. Corrija antes de empacotar.")
    os.makedirs(os.path.join(AQUI, "dist"), exist_ok=True)
    destino = os.path.join(AQUI, "dist", f"kasiski-sala-de-disputa-{m['version']}.zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=2))
        for f in ARQUIVOS:
            z.write(os.path.join(AQUI, f), f)
    print(destino)


if __name__ == "__main__":
    main()
