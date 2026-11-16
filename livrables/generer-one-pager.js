// Fabrique livrables/one-pager.pdf à partir de livrables/one-pager.html (une page, format Lettre).
// node livrables/generer-one-pager.js      (Chromium par Playwright ; les polices viennent de Google Fonts)
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dossier = __dirname;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 816, height: 1056 } });
  await p.goto('file://' + path.join(dossier, 'one-pager.html'), { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  // Rien ne doit dépasser de la page : on mesure avant d'écrire le PDF.
  const depasse = await p.evaluate(() => {
    const corps = document.querySelector('.corps'), pied = document.querySelector('.pied');
    return { contenu: Math.round(corps.scrollHeight - corps.clientHeight), page: Math.round(document.body.scrollHeight - document.body.clientHeight), piedBas: Math.round(pied.getBoundingClientRect().bottom) };
  });
  console.log('débordement (px) :', JSON.stringify(depasse));
  await p.pdf({ path: path.join(dossier, 'one-pager.pdf'), width: '8.5in', height: '11in', printBackground: true, margin: { top: '0', right: '0', bottom: '0', left: '0' }, pageRanges: '1' });
  await p.screenshot({ path: process.argv[2] || path.join(dossier, 'one-pager-apercu.png'), fullPage: false });
  await b.close();
})();
