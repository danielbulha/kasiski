// Ícones inline (sem dependência externa) e o símbolo da marca Kasiski.
// Estilo: traço (stroke), sem preenchimento — "linhas modulares", conforme o manual da marca.
// Uso: icone("nome") devolve uma string SVG pronta para entrar em qualquer template.

const _ICONES = {
  painel: '<path d="M3 3h6v8H3zM11 3h6v5h-6zM11 10h6v7h-6zM3 13h6v4H3z"/>',
  radar: '<circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3.2"/><path d="M10 3v2M10 15v2M3 10h2M15 10h2" stroke-linecap="round"/>',
  editais: '<path d="M5 2.5h7l3 3V17a.5.5 0 0 1-.5.5h-9A.5.5 0 0 1 5 17V3a.5.5 0 0 1 .5-.5Z"/><path d="M12 2.5V6h3.2M7.5 9h5M7.5 12h5M7.5 15h3"/>',
  cofre: '<rect x="4" y="8.5" width="12" height="8.5" rx="1.2"/><path d="M6.5 8.5V6a3.5 3.5 0 0 1 7 0v2.5"/><circle cx="10" cy="12.5" r="1.4"/><path d="M10 13.9V15.3"/>',
  concorrentes: '<circle cx="7" cy="6.5" r="2.6"/><path d="M2 17v-1.2A4.3 4.3 0 0 1 6.3 11.5h1.4A4.3 4.3 0 0 1 12 15.8V17"/><circle cx="14.5" cy="7.5" r="2.1"/><path d="M13.3 11.6a4 4 0 0 1 4.7 3.9V17"/>',
  pecas: '<path d="M5 2.5h6.5L15 6v10.5a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5V3a.5.5 0 0 1 .5-.5Z"/><path d="M11.2 2.5V6h3.5"/><path d="M7 10.3 12 9l-.6 1.9-4.4 4.4-2 .4.4-2Z"/>',
  agenda: '<rect x="3" y="4" width="14" height="13" rx="1.3"/><path d="M3 8h14M7 2.3v3M13 2.3v3" stroke-linecap="round"/><circle cx="7.2" cy="11.6" r=".9" fill="currentColor" stroke="none"/><circle cx="10.5" cy="11.6" r=".9" fill="currentColor" stroke="none"/><circle cx="7.2" cy="14.3" r=".9" fill="currentColor" stroke="none"/>',
  contratos: '<path d="M2.5 6.2a1.4 1.4 0 0 1 1.4-1.4h3.4l1.6 1.9h7.2A1.4 1.4 0 0 1 17.5 8v7.4a1.4 1.4 0 0 1-1.4 1.4H3.9a1.4 1.4 0 0 1-1.4-1.4Z"/>',
  precos: '<path d="M3 17V3M3 17h14" stroke-linecap="round"/><rect x="5.5" y="10.5" width="2.6" height="4.7"/><rect x="9.7" y="7" width="2.6" height="8.2"/><rect x="13.9" y="4.5" width="2.6" height="10.7"/>',
  empresa: '<path d="M4 17V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v13"/><path d="M12 8.5h3a1 1 0 0 1 1 1V17"/><path d="M6.3 6.2h1.6M6.3 9h1.6M6.3 11.8h1.6M9.3 6.2h1.6M9.3 9h1.6M9.3 11.8h1.6" stroke-linecap="round"/><path d="M7 17v-2.6h2V17"/>',
  conta: '<circle cx="10" cy="6.8" r="3.2"/><path d="M3.5 17v-1a5 5 0 0 1 5-5h3a5 5 0 0 1 5 5v1"/>',
  glossario: '<path d="M3.5 4.3c1.6-.7 3.6-.7 6 0v11c-2.4-.7-4.4-.7-6 0Z"/><path d="M16.5 4.3c-1.6-.7-3.6-.7-6 0v11c2.4-.7 4.4-.7 6 0Z"/>',
  admin: '<circle cx="10" cy="10" r="2.3"/><path d="M10 2.8v2M10 15.2v2M17.2 10h-2M4.8 10h-2M15.1 4.9l-1.4 1.4M6.3 13.7l-1.4 1.4M15.1 15.1l-1.4-1.4M6.3 6.3 4.9 4.9" stroke-linecap="round"/>',
  sair: '<path d="M8 17H4.5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1H8" stroke-linecap="round"/><path d="M12.5 13.5 16 10l-3.5-3.5M16 10H7.5" stroke-linecap="round"/>',
  adicionar: '<circle cx="10" cy="10" r="7.3"/><path d="M10 6.8v6.4M6.8 10h6.4" stroke-linecap="round"/>',
  editar: '<path d="M12.9 3.4 16.6 7.1 6.4 17.3 2.5 18l.7-3.9Z"/><path d="M11.2 5.1l3.7 3.7"/>',
  excluir: '<path d="M4 6h12M8 6V4.3a.8.8 0 0 1 .8-.8h2.4a.8.8 0 0 1 .8.8V6M6 6l.6 10a1 1 0 0 0 1 .9h4.8a1 1 0 0 0 1-.9L14 6" stroke-linecap="round"/>',
  baixar: '<path d="M10 3v10M6.3 9.3 10 13l3.7-3.7" stroke-linecap="round"/><path d="M3.5 15v1.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V15" stroke-linecap="round"/>',
  fechar: '<path d="M5 5l10 10M15 5 5 15" stroke-linecap="round"/>',
  buscar: '<circle cx="8.7" cy="8.7" r="5.4"/><path d="M16.3 16.3 12.6 12.6" stroke-linecap="round"/>',
  upload: '<path d="M10 13V3M6.3 6.7 10 3l3.7 3.7" stroke-linecap="round"/><path d="M3.5 15v1.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V15" stroke-linecap="round"/>',
  aviso: '<path d="M10 2.7 18 16.5a.9.9 0 0 1-.8 1.4H2.8a.9.9 0 0 1-.8-1.4Z"/><path d="M10 8v3.4" stroke-linecap="round"/><circle cx="10" cy="14.2" r=".95" fill="currentColor" stroke="none"/>',
  ok: '<circle cx="10" cy="10" r="7.3"/><path d="M6.7 10.2 8.8 12.3 13.3 7.7" stroke-linecap="round" stroke-linejoin="round"/>',
  menu: '<path d="M3 5.5h14M3 10h14M3 14.5h14" stroke-linecap="round"/>',
  chevronDireita: '<path d="M7.5 4.5 13 10l-5.5 5.5" stroke-linecap="round" stroke-linejoin="round"/>',
  radarPing: '<circle cx="10" cy="10" r="2"/><path d="M13.5 6.5a5 5 0 0 1 0 7M6.5 13.5a5 5 0 0 1 0-7M16 4a9 9 0 0 1 0 12M4 16a9 9 0 0 1 0-12" stroke-linecap="round"/>',
  imprimir: '<path d="M6 8V3h8v5"/><rect x="3.5" y="8" width="13" height="6" rx="1"/><path d="M6 12.5h8V17H6Z"/>',
  telefone: '<path d="M4.5 3h2.8l1 3.4-1.8 1.4a10 10 0 0 0 5.7 5.7l1.4-1.8 3.4 1v2.8a1.2 1.2 0 0 1-1.3 1.2A13.5 13.5 0 0 1 3.3 4.3 1.2 1.2 0 0 1 4.5 3Z"/>',
  olho: '<path d="M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10Z"/><circle cx="10" cy="10" r="2.3"/>',
  restaurar: '<path d="M4.2 8.5A6.3 6.3 0 1 1 5 13.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 4.3v4.3h4.3" stroke-linecap="round" stroke-linejoin="round"/>',
  atualizar: '<path d="M15.8 8.5V4.2h-4.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M15.8 11.5a6.3 6.3 0 1 1-.8-4.7" stroke-linecap="round" stroke-linejoin="round"/>',
};

function icone(nome, tamanho = 18) {
  const miolo = _ICONES[nome];
  if (!miolo) return "";
  return `<svg width="${tamanho}" height="${tamanho}" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${miolo}</svg>`;
}

// Símbolo da marca: interpretação do "padrão emergindo de dados" descrito no manual
// (grade de traços de comprimentos variados, majoritariamente escuros com destaques em ciano).
// Provisório até o arquivo vetorial oficial ser recebido — ver README.
function simboloMarca(tamanho = 28) {
  return `<svg width="${tamanho}" height="${Math.round(tamanho * 44 / 62)}" viewBox="0 0 62 44" fill="currentColor" aria-hidden="true">
    <rect x="0" y="2" width="12" height="5" rx="2.5"/><rect x="16" y="2" width="7" height="5" rx="2.5"/>
    <rect x="27" y="2" width="18" height="5" rx="2.5" fill="#11B8C8"/><rect x="49" y="2" width="9" height="5" rx="2.5"/>
    <rect x="4" y="11" width="17" height="5" rx="2.5"/><rect x="25" y="11" width="10" height="5" rx="2.5"/><rect x="39" y="11" width="7" height="5" rx="2.5"/>
    <rect x="0" y="20" width="9" height="5" rx="2.5"/><rect x="13" y="20" width="14" height="5" rx="2.5" fill="#11B8C8"/><rect x="31" y="20" width="9" height="5" rx="2.5"/><rect x="44" y="20" width="12" height="5" rx="2.5"/>
    <rect x="6" y="29" width="15" height="5" rx="2.5"/><rect x="25" y="29" width="7" height="5" rx="2.5"/><rect x="36" y="29" width="14" height="5" rx="2.5"/>
    <rect x="0" y="38" width="7" height="5" rx="2.5"/><rect x="11" y="38" width="19" height="5" rx="2.5"/><rect x="34" y="38" width="9" height="5" rx="2.5"/>
  </svg>`;
}
