// Captures réelles du site pour les diapositives 4 et 5 de la présentation d'entrée.
//
//   cd web && npm run dev            (dans un autre terminal ; le serveur d'analyse n'est pas nécessaire)
//   node scripts/captures.js [http://localhost:3000]
//   python3 scripts/captures_webp.py   (PNG -> WebP dans public/presentation/)
//
// À relancer quand l'apparence des diapositives de résultat change. Les images montrent la démonstration
// de Robert, donc des données de agents/sorties/robert.json : rien n'est maquetté.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const URL = process.argv[2] || "http://localhost:3000";
const SORTIE = path.join(__dirname, "..", "public", "presentation");

(async () => {
  fs.mkdirSync(SORTIE, { recursive: true });
  const navigateur = await chromium.launch();
  const page = await navigateur.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
  // Présentation déjà vue ; sur un site avec comptes, EAGLE_SESSION porte une session (JSON de lib/compte.ts).
  await page.addInitScript((session) => {
    localStorage.setItem("eagle:intro-vue", "1");
    if (session) localStorage.setItem("eagle:session", session);
  }, process.env.EAGLE_SESSION || null);
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.locator(".demo", { hasText: "Robert" }).click();
  await page.waitForSelector(".diapo__plan");
  const centre = page.locator(".eagle__centre");

  await page.locator(".diapo__point", { hasText: "Répartition" }).click();
  await page.waitForTimeout(1400);
  await page.locator(".anneau__entree", { hasText: "Obligations" }).first().hover();
  await page.waitForTimeout(400);
  await centre.screenshot({ path: path.join(SORTIE, "repartition.png") });

  await page.locator(".diapo__point", { hasText: "Pourquoi vous" }).click();
  await page.waitForTimeout(900);
  await page.locator(".diapo .chiffre").first().click();
  await page.waitForSelector(".fiche");
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SORTIE, "chiffre.png"), clip: { x: 300, y: 60, width: 840, height: 780 } });
  await page.keyboard.press("Escape");
  if (await page.locator(".fiche").count()) await page.mouse.click(20, 20);

  await page.locator("#saisie").fill("et Tesla ?");
  await page.locator(".champ__envoyer").click();
  await page.waitForSelector(".diapo-actif .puce, .diapo-actif .diapo__manque", { timeout: 60000 });
  await page.waitForTimeout(600);
  await centre.screenshot({ path: path.join(SORTIE, "actif.png") });

  const dossier = await navigateur.newPage({ viewport: { width: 1000, height: 760 }, deviceScaleFactor: 1.5 });
  await dossier.goto(`${URL}/rapport/?persona=robert&imprimer=0`, { waitUntil: "networkidle" });
  await dossier.waitForSelector(".dossier__camembert svg");
  await dossier.evaluate(() => { document.querySelector(".dossier__ecran").scrollTop = 560; });
  await dossier.waitForTimeout(400);
  await dossier.screenshot({ path: path.join(SORTIE, "dossier.png") });
  await navigateur.close();
  console.log("Captures écrites dans", SORTIE);
})();
