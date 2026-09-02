#!/usr/bin/env python3
"""Genere docs/schemas.html a partir des blocs Mermaid des fichiers .md.

POURQUOI CE SCRIPT EXISTE
La page a ete ecrite a la main pendant un temps, et elle a derive : elle a
affiche 8 schemas quand les documents en contenaient 15, puis 11 quand ils en
contenaient 17, avec des diagrammes dont le contenu avait change entre-temps.
Meme cause que pour les releves de donnees : ce qui est recopie diverge.
La source de verite reste les .md ; cette page n'en est que le rendu.

La bibliotheque Mermaid est embarquee dans la page, qui reste donc consultable
hors ligne, sans extension et sans reseau.

Usage : python docs/build_schemas.py
        python docs/build_schemas.py --verifier   sort en erreur si la page est
                                                  en retard, sans rien ecrire
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOCS = RACINE / "docs"
CIBLE = DOCS / "schemas.html"

# La bibliotheque Mermaid n'est stockee qu'UNE fois : a l'interieur de la page
# elle-meme. Elle y etait deja, et en garder une seconde copie dans docs/vendor/
# doublait le poids du depot (3,2 Mo x 2) sans rien apporter.
# Le generateur la relit donc dans la page courante avant de la reecrire.


def lire_bundle() -> str:
    """Extrait la bibliotheque Mermaid embarquee dans la page existante."""
    if not CIBLE.exists():
        raise SystemExit(
            f"ERREUR : {CIBLE.name} est absent, or il porte la bibliotheque Mermaid.\n"
            f"         Recuperez-le : git checkout -- docs/schemas.html")
    s = CIBLE.read_text(encoding="utf-8")
    try:
        i = s.rindex("</footer>")
        a = s.index("<script>", i) + len("<script>")
        b = s.index("</script>", a)
    except ValueError:
        raise SystemExit(
            f"ERREUR : bibliotheque Mermaid introuvable dans {CIBLE.name}.\n"
            f"         La page est corrompue. Recuperez-la : git checkout -- docs/schemas.html")
    bundle = s[a:b].strip()
    if len(bundle) < 500_000:
        raise SystemExit(f"ERREUR : bibliotheque suspecte, {len(bundle)} octets seulement.")
    return bundle + "\n"

# (fichier source, index du bloc dans ce fichier, titre, etiquette, legende)
MANIFESTE = [
    ("conception/00_architecture.md", 0, "Architecture globale", "structurelle",
     "Un serveur MCP unique, ouvert sur ses composants, avec ingestion hors ligne."),
    ("conception/06_choix_stockage.md", 0, "Les quatre supports de stockage", "chantier 6",
     "Une base relationnelle lue seulement, deux index reconstructibles, un fichier d'ajout."),
    ("analyse_donnees.md", 0, "Modele relationnel de la base metier", "donnees",
     "Six tables, cles etrangeres, et les trois colonnes sensibles interdites au support."),
    ("conception/01_flux_chunks.md", 0, "Flux d'ingestion, par artefacts", "chantier 1",
     "Chaque etape affiche son entree et sa sortie. Les cardinalites sont symboliques."),
    ("conception/01_flux_chunks.md", 1, "Modele de donnees Document / Chunk", "chantier 1",
     "Les metadonnees de citation sont copiees dans le chunk, ce qui rend E1 mecanique."),
    ("conception/01_flux_chunks.md", 2, "Le modele sur un cas reel", "chantier 1",
     "Une reference, trois documents, six chunks. Le versionnage se fait par type."),
    ("conception/01_flux_chunks.md", 3, "Flux de recherche, l'entonnoir", "E1 - E2",
     "La decroissance est la regle. Le modele le plus couteux ne voit que la preselection."),
    ("conception/02_tools_text2sql.md", 0, "Chemin Text-to-SQL", "chantier 2",
     "Routage vers un tool fige ou vers la generation, et les trois sorties du modele."),
    ("conception/02_tools_text2sql.md", 1, "Jointures canoniques", "chantier 2",
     "Les quatre seuls chemins, avec leur predicat. Premiere cause d'erreur du SQL genere."),
    ("conception/02_tools_text2sql.md", 2, "Pile de gardes lecture seule", "E3",
     "Chaque couche couvre une defaillance differente. La connexion est le garde-fou ultime."),
    ("conception/02_tools_text2sql.md", 3, "Schema montre a chaque profil", "E5",
     "Ce que le support recoit dans son prompt : il ne voit pas exister les colonnes sensibles."),
    ("conception/03_matrice_acces.md", 0, "Arbre de decision des tools SQL", "chantier 3",
     "Ce que le mini guide d'acces donne au client pour choisir le bon tool."),
    ("conception/03_matrice_acces.md", 1, "Matrice appliquee aux deux niveaux", "E4 - E5",
     "Tool a l'entree, ressources dans le tool, journal dans tous les cas."),
    ("conception/07_cible_deploiement.md", 0, "Architecture cible sur Azure", "chantier 7",
     "Quatre unites deployees. Le bot Slack est entre l'utilisateur et la Gateway."),
    ("conception/08_interface.md", 0, "Interface de demonstration : deux profils", "chantier 8",
     "Deux processus, meme image et meme matrice, journal partage. E4 rendu visible."),
    ("conception/04_sequences.md", 0, "Question documentaire : reponse ou abstention", "E1 - E2",
     "answer_question : hybride, reranking, seuil, sources citees ou abstention."),
    ("conception/04_sequences.md", 1, "Text-to-SQL autorise : gardes lecture seule", "E3",
     "ask_database : generation, AST, perimetre, LIMIT, execution read-only, SQL renvoye."),
    ("conception/04_sequences.md", 2, "Colonne sensible pour le support : refus", "E5",
     "Le perimetre rattrape meme si le modele produit un SQL touchant une colonne interdite."),
    ("conception/04_sequences.md", 3, "Appel non autorise au niveau tool", "E4",
     "Le refus intervient a l'entree, aucun moteur n'est atteint."),
    ("conception/04_sequences.md", 4, "Tentative d'ecriture : lecture seule", "E3",
     "L'AST rejette le non-SELECT, la connexion read-only reste le garde-fou ultime."),
]

FENCE = re.compile(r"```mermaid\r?\n(.*?)```", re.S)


def blocs(chemin: Path) -> list[str]:
    return [m.group(1).rstrip() for m in FENCE.finditer(chemin.read_text(encoding="utf-8"))]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


HEAD = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sorabel Data Gateway — Schémas</title>
<style>
  :root { --bg:#f6f7f9; --fg:#1c2024; --muted:#5b6470; --card:#fff; --line:#e3e6ea; --accent:#2f6f4f; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1216; --fg:#e6e8eb; --muted:#9aa4b0; --card:#fff; --line:#232a31; --accent:#57c08a; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); line-height:1.55;
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  header, nav, main, footer { max-width:1180px; margin:0 auto; padding-left:24px; padding-right:24px; }
  header { padding-top:34px; padding-bottom:4px; }
  header h1 { margin:0 0 6px; font-size:1.65rem; letter-spacing:-.01em; }
  header p { margin:0; color:var(--muted); }
  nav { padding-top:14px; }
  nav ol { margin:0; padding:0 0 0 1.2em; columns:2; column-gap:30px; font-size:.87rem; }
  nav a { color:var(--accent); text-decoration:none; }
  nav a:hover { text-decoration:underline; }
  main { padding-top:8px; padding-bottom:52px; }
  section { background:var(--card); border:1px solid var(--line); border-radius:12px;
            padding:18px 20px 22px; margin:20px 0; box-shadow:0 1px 2px rgba(0,0,0,.05);
            scroll-margin-top:16px; }
  section h2 { margin:0 0 3px; font-size:1.05rem; color:#1c2024; }
  section p.cap { margin:0 0 12px; color:#5b6470; font-size:.9rem; }
  section p.src { margin:12px 0 0; color:#8a929c; font-size:.78rem;
                  font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
  .mermaid { overflow-x:auto; text-align:center; }
  .tag { display:inline-block; font-size:.72rem; font-weight:600; color:#fff; background:var(--accent);
         border-radius:999px; padding:2px 9px; margin-left:8px; vertical-align:middle; white-space:nowrap; }
  footer { padding-bottom:42px; color:var(--muted); font-size:.82rem; }
  #alerte { max-width:1180px; margin:16px auto 0; padding:14px 18px; border-radius:10px;
            background:#fff4e5; border:1px solid #f0c48a; color:#6b4415; font-size:.92rem; }
  @media (max-width:820px) { nav ol { columns:1; } }
</style>
</head>
<body>
<header>
  <h1>Sorabel Data Gateway — Vues schématisées</h1>
  <p>{n} schémas, extraits des fichiers du dossier de conception le {d}.</p>
</header>
<div id="alerte">
  <b>Les schémas ne s'affichent pas ?</b> Cette page a besoin d'exécuter du JavaScript.
  La prévisualisation HTML de VSCode le bloque et n'afficherait que du code Mermaid brut.
  Ouvrez <code>docs/schemas.html</code> dans un navigateur. Ce message disparaît dès que
  le rendu fonctionne.
</div>
"""

PIED = """</main>
<footer>
  Page <strong>générée</strong> par <code>python docs/build_schemas.py</code> depuis les blocs Mermaid
  des <code>.md</code>. Ne pas l'éditer à la main : modifier le document source indiqué sous chaque
  schéma, puis relancer le script. <code>--verifier</code> signale une page en retard.
</footer>
<script>
"""

RUN = """</script>
<script>
  (function () {
    function rendre() {
      var al = document.getElementById('alerte');
      if (al) al.remove();
      try {
        mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default',
                             flowchart: { useMaxWidth: true, htmlLabels: true },
                             sequence: { useMaxWidth: true },
                             er: { useMaxWidth: true } });
        mermaid.run();
      } catch (e) {
        document.body.insertAdjacentHTML('beforeend',
          '<pre style="color:#b00;padding:16px">Erreur de rendu Mermaid : ' + e + '</pre>');
      }
    }
    if (document.readyState === 'complete' || document.readyState === 'interactive') rendre();
    else window.addEventListener('DOMContentLoaded', rendre);
  })();
</script>
</body>
</html>
"""


def rendu() -> str:
    cache: dict[str, list[str]] = {}
    items = []
    for rel, idx, titre, tag, cap in MANIFESTE:
        src = DOCS / rel
        if not src.exists():
            raise SystemExit(f"ERREUR : source introuvable ({src})")
        bs = cache.setdefault(rel, blocs(src))
        if idx >= len(bs):
            raise SystemExit(f"ERREUR : {rel} contient {len(bs)} diagramme(s), index {idx} demande")
        items.append((rel, idx, titre, tag, cap, bs[idx]))

    p = [HEAD.replace("{n}", str(len(items))).replace("{d}", date.today().isoformat()), "<nav><ol>"]
    for i, (_, _, titre, _, _, _) in enumerate(items, 1):
        p.append(f'<li><a href="#s{i}">{esc(titre)}</a></li>')
    p.append("</ol></nav>\n<main>\n")
    for i, (rel, idx, titre, tag, cap, code) in enumerate(items, 1):
        p.append(
            f'  <section id="s{i}">\n'
            f'    <h2>{i}. {esc(titre)} <span class="tag">{esc(tag)}</span></h2>\n'
            f'    <p class="cap">{esc(cap)}</p>\n'
            f'    <pre class="mermaid">\n{esc(code)}\n    </pre>\n'
            f'    <p class="src">source : docs/{rel}, diagramme {idx + 1}</p>\n'
            f"  </section>\n\n"
        )
    p.append(PIED)
    p.append(lire_bundle())
    p.append(RUN)
    return "".join(p)


def sans_date(s: str) -> str:
    return re.sub(r"le \d{4}-\d{2}-\d{2}", "le DATE", s)


def main() -> int:
    neuf = rendu()
    if "--verifier" in sys.argv:
        ancien = CIBLE.read_text(encoding="utf-8") if CIBLE.exists() else ""
        if sans_date(ancien) == sans_date(neuf):
            print("schemas.html a jour")
            return 0
        print("SCHEMAS.HTML EN RETARD : relancer python docs/build_schemas.py", file=sys.stderr)
        return 1
    CIBLE.write_text(neuf, encoding="utf-8", newline="\n")
    n = neuf.count('class="mermaid"')
    print(f"docs/schemas.html : {n} schemas, {CIBLE.stat().st_size / 1024 / 1024:.2f} Mo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
