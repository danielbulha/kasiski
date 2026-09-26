// Rastreamento do Kasiski (site público e app): visitor_id, primeiro/último toque (UTMs, gclid, ref de parceiro),
// consentimento de cookies (LGPD) com Google Consent Mode v2, Data Layer e carregamento das tags (GTM ou diretas).
// IDs em CERTAME.TAGS (js/config.js). Sem ID preenchido, nenhuma tag de terceiros é carregada.
(() => {
  const CFG = (window.CERTAME && CERTAME.TAGS) || {};
  const API = (window.CERTAME && CERTAME.API_URL) || "";
  // Armazenamento compartilhado entre kasiski.com.br e app.kasiski.com.br: cookie próprio no domínio-pai
  // (o localStorage é separado por subdomínio). Valores antigos do localStorage são migrados na primeira leitura.
  const DOMINIO = /(^|\.)kasiski\.com\.br$/.test(location.hostname) ? ".kasiski.com.br" : "";
  const lerCookie = (k) => { const m = document.cookie.match(new RegExp("(?:^|; )" + k + "=([^;]*)")); try { return m ? decodeURIComponent(m[1]) : null; } catch { return null; } };
  const gravarCookie = (k, v, dias = 400) => {
    document.cookie = `${k}=${encodeURIComponent(v)}; path=/; max-age=${Math.round(dias * 86400)}; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}${DOMINIO ? "; domain=" + DOMINIO : ""}`;
  };
  const ler = (k) => {
    const c = lerCookie(k);
    if (c !== null) return c;
    try { const v = localStorage.getItem(k); if (v !== null) gravarCookie(k, v); return v; } catch { return null; }
  };
  const gravar = (k, v, dias) => { gravarCookie(k, v, dias); try { localStorage.setItem(k, v); } catch { /* navegação privada */ } };
  const apagar = (k) => { gravarCookie(k, "", 0); try { localStorage.removeItem(k); } catch { /* ok */ } };
  const lerJson = (k) => { try { return JSON.parse(ler(k) || "null"); } catch { return null; } };
  // mesmo site = kasiski.com.br, www e app (e localhost em desenvolvimento): não conta como origem externa
  const base = (h) => (h || "").replace(/^(www|app)\./, "");

  // ------------------------------------------------------------ visitor_id (primeira parte, sem dado pessoal)
  let vid = ler("kasiski_visitante");
  if (!vid) { vid = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)).slice(0, 36); gravar("kasiski_visitante", vid); }

  // ------------------------------------------------------------ toques (atribuição)
  const q = new URLSearchParams(location.search || (location.hash.includes("?") ? location.hash.split("?")[1] : ""));
  let referrer = "";
  try { const h = document.referrer ? new URL(document.referrer).hostname : ""; referrer = h && base(h) !== base(location.hostname) ? document.referrer : ""; } catch { /* ignora */ }
  const CAMPOS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid", "li_fat_id", "ref"];
  const atual = {};
  CAMPOS.forEach((k) => { const v = q.get(k); if (v) atual[k] = v.slice(0, 200); });
  if (["site", "lp", "interno"].includes((atual.utm_source || "").toLowerCase())) CAMPOS.forEach((k) => { if (k !== "ref") delete atual[k]; });
  const temOrigem = Object.keys(atual).length > 0 || !!referrer;
  const toque = temOrigem ? { ...atual, landing: location.pathname + (location.hash && location.hash.length < 60 ? location.hash.split("?")[0] : ""), referrer: referrer.slice(0, 300), em: new Date().toISOString() } : null;
  if (toque) {
    if (!lerJson("kasiski_primeiro_toque")) gravar("kasiski_primeiro_toque", JSON.stringify(toque));
    gravar("kasiski_ultimo_toque", JSON.stringify(toque));
  } else if (!lerJson("kasiski_primeiro_toque")) {
    gravar("kasiski_primeiro_toque", JSON.stringify({ landing: location.pathname, em: new Date().toISOString() }));
  }
  if (atual.ref) gravar("kasiski_ref", atual.ref);
  // compatibilidade com o funil antigo (origem/campanha do primeiro toque)
  const p0 = lerJson("kasiski_primeiro_toque") || {};
  if (!ler("kasiski_origem") && (p0.utm_source || p0.referrer)) { try { gravar("kasiski_origem", p0.utm_source || new URL(p0.referrer).hostname); } catch { /* ignora */ } }
  if (!ler("kasiski_campanha") && p0.utm_campaign) gravar("kasiski_campanha", p0.utm_campaign);

  // ------------------------------------------------------------ consentimento + Consent Mode v2
  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;
  const CHAVE = "kasiski_consentimento";
  let consent = lerJson(CHAVE);
  const estado = (c) => ({
    analytics_storage: c && c.analytics ? "granted" : "denied",
    ad_storage: c && c.marketing ? "granted" : "denied",
    ad_user_data: c && c.marketing ? "granted" : "denied",
    ad_personalization: c && c.marketing ? "granted" : "denied",
  });
  gtag("consent", "default", { ...estado(consent), functionality_storage: "granted", security_storage: "granted", wait_for_update: 500 });
  dataLayer.push({ kasiski_visitor_id: vid });

  function carregar(src, id) {
    if (id && document.getElementById(id)) return;
    const s = document.createElement("script"); s.async = true; s.src = src; if (id) s.id = id;
    document.head.appendChild(s);
  }
  let gtmCarregado = false, diretasAnalytics = false, diretasMarketing = false;
  function aplicarTags() {
    // GTM entra sempre que houver ID: as tags internas respeitam o Consent Mode (configure "consentimento adicional" no GTM)
    if (CFG.GTM_ID && !gtmCarregado) {
      gtmCarregado = true;
      dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
      carregar(`https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(CFG.GTM_ID)}`, "gtm");
    }
    if (CFG.GTM_ID) return; // com GTM, GA4/Ads/LinkedIn/Meta são configurados dentro dele
    if (consent?.analytics && CFG.GA4_ID && !diretasAnalytics) {
      diretasAnalytics = true;
      carregar(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(CFG.GA4_ID)}`, "gtag");
      gtag("js", new Date()); gtag("config", CFG.GA4_ID, { user_properties: { kasiski_visitor_id: vid } });
    }
    if (consent?.marketing && !diretasMarketing) {
      diretasMarketing = true;
      if (CFG.GOOGLE_ADS_ID) { carregar(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(CFG.GOOGLE_ADS_ID)}`, "gtag-ads"); gtag("js", new Date()); gtag("config", CFG.GOOGLE_ADS_ID); }
      if (CFG.LINKEDIN_PARTNER_ID) {
        window._linkedin_partner_id = CFG.LINKEDIN_PARTNER_ID;
        window._linkedin_data_partner_ids = [CFG.LINKEDIN_PARTNER_ID];
        carregar("https://snap.licdn.com/li.lms-analytics/insight.min.js", "li-insight");
      }
      if (CFG.META_PIXEL_ID && !window.fbq) {
        const f = window.fbq = function () { f.callMethod ? f.callMethod.apply(f, arguments) : f.queue.push(arguments); };
        f.push = f; f.loaded = true; f.version = "2.0"; f.queue = [];
        carregar("https://connect.facebook.net/en_US/fbevents.js", "fb-pixel");
        fbq("init", CFG.META_PIXEL_ID); fbq("track", "PageView");
      }
    }
  }

  function salvarConsentimento(c) {
    consent = { necessarios: true, analytics: !!c.analytics, marketing: !!c.marketing, em: new Date().toISOString(), versao: 1 };
    gravar(CHAVE, JSON.stringify(consent), 365);
    gtag("consent", "update", estado(consent));
    dataLayer.push({ event: "consent_update", consent_analytics: consent.analytics, consent_marketing: consent.marketing });
    aplicarTags();
    fecharBanner();
  }

  // ------------------------------------------------------------ banner
  const estilo = document.createElement("style");
  estilo.textContent = `.kc-banner{position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483000;display:flex;justify-content:center;pointer-events:none}
    .kc-caixa{pointer-events:auto;max-width:720px;width:100%;background:#071D2D;color:#fff;border-radius:12px;padding:16px 18px;box-shadow:0 12px 40px rgba(7,29,45,.35);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}
    .kc-caixa p{margin:0 0 10px}.kc-caixa a{color:#7fdde6}.kc-opcoes{display:grid;gap:6px;margin:0 0 12px}.kc-opcoes[hidden]{display:none}.kc-opcoes label{display:flex;gap:8px;align-items:center;justify-content:flex-start;text-align:left}.kc-opcoes input{width:auto;margin:0;flex:none}
    .kc-opcoes small{opacity:.6}.kc-botoes{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}
    .kc-botoes button{font:inherit;font-weight:700;border-radius:6px;padding:8px 14px;border:1px solid rgba(255,255,255,.35);background:transparent;color:#fff;cursor:pointer}
    .kc-botoes .kc-principal{background:#11B8C8;border-color:#11B8C8;color:#071D2D}
    @media (max-width:560px){.kc-botoes button{flex:1 1 100%}}`;
  document.head.appendChild(estilo);
  let banner;
  function fecharBanner() { if (banner) { banner.remove(); banner = null; } }
  function abrirBanner(detalhes) {
    fecharBanner();
    banner = document.createElement("div");
    banner.className = "kc-banner";
    banner.setAttribute("role", "dialog"); banner.setAttribute("aria-label", "Preferências de cookies");
    const c = consent || { analytics: true, marketing: false };
    banner.innerHTML = `<div class="kc-caixa">
      <p><b>Cookies e privacidade.</b> Usamos cookies necessários para o site funcionar e, com a sua permissão, cookies de medição
        (para entender o uso do site) e de marketing (para mostrar anúncios relevantes). <a href="${(window.CERTAME && CERTAME.SITE_URL) || ""}/cookies/">Saiba mais</a>.</p>
      <div class="kc-opcoes" ${detalhes ? "" : "hidden"}>
        <label><input type="checkbox" checked disabled> Necessários <small>sempre ativos</small></label>
        <label><input type="checkbox" data-kc="analytics" ${c.analytics ? "checked" : ""}> Medição (Google Analytics)</label>
        <label><input type="checkbox" data-kc="marketing" ${c.marketing ? "checked" : ""}> Marketing (Google Ads, LinkedIn, Meta)</label>
      </div>
      <div class="kc-botoes">
        <button type="button" data-kc-acao="necessarios">Somente necessários</button>
        <button type="button" data-kc-acao="${detalhes ? "salvar" : "personalizar"}">${detalhes ? "Salvar escolhas" : "Personalizar"}</button>
        <button type="button" data-kc-acao="todos" class="kc-principal">Aceitar todos</button>
      </div></div>`;
    document.body.appendChild(banner);
    banner.querySelector('[data-kc-acao="necessarios"]').onclick = () => salvarConsentimento({ analytics: false, marketing: false });
    banner.querySelector('[data-kc-acao="todos"]').onclick = () => salvarConsentimento({ analytics: true, marketing: true });
    const b2 = banner.querySelector('[data-kc-acao="personalizar"],[data-kc-acao="salvar"]');
    b2.onclick = () => {
      if (b2.dataset.kcAcao === "personalizar") { abrirBanner(true); return; }
      salvarConsentimento({ analytics: banner.querySelector('[data-kc="analytics"]').checked, marketing: banner.querySelector('[data-kc="marketing"]').checked });
    };
  }
  const iniciarBanner = () => { if (!consent) abrirBanner(false); aplicarTags(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciarBanner); else iniciarBanner();
  document.addEventListener("click", (ev) => { if (ev.target.closest("[data-preferencias-cookies]")) { ev.preventDefault(); abrirBanner(true); } });

  // ------------------------------------------------------------ eventos
  const PRIMEIRA_PARTE = new Set(["page_view", "cta_click", "pricing_view", "lead_form_start", "tool_started", "tool_completed",
    "checklist_download", "diagnostic_completed", "radar_result_viewed"]);
  const enviados = new Set();
  function evento(nome, params = {}) {
    dataLayer.push({ event: nome, ...params, kasiski_visitor_id: vid });
    if (!CFG.GTM_ID && consent?.analytics && CFG.GA4_ID && window.gtag) gtag("event", nome, params);
    if (!CFG.GTM_ID && consent?.marketing && window.fbq && ["generate_lead", "sign_up", "purchase"].includes(nome))
      fbq("track", { generate_lead: "Lead", sign_up: "CompleteRegistration", purchase: "Purchase" }[nome]);
    // medição própria (sem dado pessoal) — desligada se o visitante recusar a medição
    if (!PRIMEIRA_PARTE.has(nome) || (consent && consent.analytics === false)) return;
    const chave = nome + "|" + (params.pagina || location.pathname + location.hash) + "|" + (params.cta || "");
    if (enviados.has(chave)) return;
    enviados.add(chave);
    const ultimo = lerJson("kasiski_ultimo_toque");
    fetch(API + "/api/public/eventos", {
      method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
      body: JSON.stringify({ tipo: nome, visitante: vid, toque: toque || ultimo || p0, pagina: params.pagina || location.pathname + (location.hash || ""), dados: params }),
    }).catch(() => { /* medição é acessória */ });
  }

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-cta], a[href*='#/cadastro']");
    if (el) evento("cta_click", { cta: el.dataset.cta || (el.textContent || "").trim().slice(0, 60), pagina: location.pathname + location.hash });
  });

  window.Kasiski = {
    visitante: vid,
    evento,
    aquisicao: () => ({ primeiro: lerJson("kasiski_primeiro_toque"), ultimo: lerJson("kasiski_ultimo_toque") }),
    toque: () => toque || lerJson("kasiski_ultimo_toque") || p0,
    consentimento: () => consent,
    abrirPreferencias: () => abrirBanner(true),
    ler, gravar, apagar, lerJson,
  };
})();
