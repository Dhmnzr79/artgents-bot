/** Local decorative icons. Keys describe authored actions, never inferred label text. */
const shapes = {
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  send: '<path d="m21 3-7.1 18-3.8-7.1L3 10.1 21 3Z"/><path d="m10.1 13.9 6.2-6.2"/>',
  question: '<path d="M20 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 18 0Z"/><path d="M9 8a2 2 0 1 1 3 1.7c-.9.5-1 1-1 1.8M11 15h.01"/>',
  services: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  prices: '<path d="M3 4h8l10 10-7 7L3 10V4Z"/><circle cx="7" cy="8" r=".6"/>',
  doctors: '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  video: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3V9Z"/>',
  results: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  booking: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18m-13 5h3m-3 3h6"/>',
  promotion: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v9h14v-9M12 8v13M12 8H8a3 3 0 1 1 3-3l1 3Zm0 0h4a3 3 0 1 0-3-3l-1 3Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
  wallet: '<path d="M20 7H5a2 2 0 0 1 0-4h13v4M3 5v14a2 2 0 0 0 2 2h15V7M20 11h-5a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h5M16 14h.01"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
};
export const MENU_ICON_KEYS = Object.freeze(['question','services','prices','doctors','video','results','booking','promotion','info']);
export const ARROW_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes.arrow}</svg>`;
export const SEND_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${shapes.send}</svg>`;
export function createWidgetIcon(key, className = '', direction = 'right') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');
  svg.setAttribute('stroke-width','1.5');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');
  svg.setAttribute('aria-hidden','true');if(className)svg.setAttribute('class',className);
  svg.innerHTML = Object.hasOwn(shapes,key) ? shapes[key] : shapes.question;
  if(direction==='left')svg.style.transform='rotate(180deg)';
  return svg;
}
