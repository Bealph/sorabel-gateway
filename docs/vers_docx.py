#!/usr/bin/env python3
"""Convertit un Markdown en document Word, avec la bibliothèque standard seule.

    uv run python docs/vers_docx.py docs/manuel_pedagogique.md

POURQUOI CE SCRIPT EXISTE
Le livrable demandé est un `.docx`. Les deux outils habituels sont indisponibles
sur ce poste :

- `python-docx` échoue à l'import : sa dépendance `lxml` charge une DLL que
  **Smart App Control** refuse (« une stratégie de contrôle d'application a
  bloqué ce fichier »). C'est le même verrou qui avait bloqué le Python d'`uv`
  au lot 0, et il ne se désactive pas sans réinstaller Windows ;
- `pandoc` n'est pas installé, et l'installer demanderait un téléchargement de
  plus sur un poste déjà contraint.

Or un `.docx` n'est **rien d'autre qu'une archive ZIP de fichiers XML**, décrite
par la norme OOXML. `zipfile` et `xml` suffisent donc, sans aucune dépendance,
sans DLL, et sans rien demander à l'administrateur du poste.

CE QUE LE MANUEL RESTE
Le Markdown est la **source**, versionnée et lisible en diff. Le Word est
**généré**, jamais édité à la main : c'est la règle qui structure tout ce dépôt,
« ce qui est recopié dérive ». Corriger le manuel, c'est corriger le `.md` puis
relancer ce script.

LE SOUS-ENSEMBLE MARKDOWN RECONNU
Titres `#` à `####`, paragraphes, listes à puces et numérotées, tableaux,
blocs de code encadrés, citations `>`, et en ligne : `**gras**`, `*italique*`,
`` `code` ``. Tout le reste est rendu littéralement, ce qui est préférable à un
rendu approximatif et silencieux.
"""
from __future__ import annotations

import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: Les couleurs sont volontairement sobres : un manuel se lit et s'imprime, il
#: ne se contemple pas.
BLEU = "1F3B57"
GRIS = "595959"
FOND_CODE = "F4F4F4"


# --------------------------------------------------------------- morceaux XML
def _texte_courant(fragment: str) -> str:
    """Le texte en ligne, avec gras, italique et code, en `runs` Word.

    On coupe sur les marqueurs plutôt que d'analyser récursivement : un manuel
    n'a pas besoin de gras dans du code, et une analyse simple qui échoue
    visiblement vaut mieux qu'une analyse subtile qui échoue en silence.
    """
    sortie: list[str] = []
    motif = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    for morceau in motif.split(fragment):
        if not morceau:
            continue
        if morceau.startswith("**") and morceau.endswith("**"):
            sortie.append(_run(morceau[2:-2], gras=True))
        elif morceau.startswith("*") and morceau.endswith("*") and len(morceau) > 2:
            sortie.append(_run(morceau[1:-1], italique=True))
        elif morceau.startswith("`") and morceau.endswith("`"):
            sortie.append(_run(morceau[1:-1], code=True))
        else:
            sortie.append(_run(morceau))
    return "".join(sortie)


def _run(texte: str, *, gras: bool = False, italique: bool = False,
         code: bool = False, couleur: str = "", taille: int = 0) -> str:
    props = []
    if code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
        props.append(f'<w:shd w:val="clear" w:fill="{FOND_CODE}"/>')
    if gras:
        props.append("<w:b/>")
    if italique:
        props.append("<w:i/>")
    if couleur:
        props.append(f'<w:color w:val="{couleur}"/>')
    if taille:
        props.append(f'<w:sz w:val="{taille * 2}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    # `xml:space="preserve"` sinon Word mange les espaces de bord, et le code
    # indente perd son alignement.
    return (f"<w:r>{rpr}<w:t xml:space=\"preserve\">{escape(texte)}</w:t></w:r>")


def _paragraphe(contenu: str, *, style: str = "", saut_avant: bool = False,
                garder_avec_suivant: bool = False) -> str:
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    if saut_avant:
        props.append('<w:pageBreakBefore/>')
    if garder_avec_suivant:
        props.append("<w:keepNext/>")
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
    return f"<w:p>{ppr}{contenu}</w:p>"


def _ligne_code(texte: str) -> str:
    bordure = ('<w:pBdr><w:left w:val="single" w:sz="18" w:space="4" '
               f'w:color="{BLEU}"/></w:pBdr>')
    return ("<w:p><w:pPr><w:pStyle w:val=\"Code\"/>"
            f"{bordure}<w:shd w:val=\"clear\" w:fill=\"{FOND_CODE}\"/>"
            "<w:spacing w:after="
            "\"0\"/></w:pPr>" + _run(texte or " ", code=True) + "</w:p>")


def _tableau(lignes: list[list[str]]) -> str:
    """Un tableau simple, première ligne en en-tête."""
    largeur = 9000 // max(1, len(lignes[0]))
    bord = ('<w:tblBorders>'
            + "".join(f'<w:{c} w:val="single" w:sz="4" w:color="BFBFBF"/>'
                      for c in ("top", "left", "bottom", "right",
                                "insideH", "insideV"))
            + "</w:tblBorders>")
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/>{bord}</w:tblPr>']
    for i, ligne in enumerate(lignes):
        out.append("<w:tr>")
        for cellule in ligne:
            fond = (f'<w:shd w:val="clear" w:fill="{FOND_CODE}"/>' if i == 0
                    else "")
            corps = (_run(re.sub(r"[*`]", "", cellule), gras=True) if i == 0
                     else _texte_courant(cellule))
            out.append(f'<w:tc><w:tcPr><w:tcW w:w="{largeur}" w:type="dxa"/>'
                       f'{fond}</w:tcPr>'
                       f'<w:p><w:pPr><w:spacing w:after="40"/></w:pPr>'
                       f'{corps}</w:p></w:tc>')
        out.append("</w:tr>")
    out.append("</w:tbl>")
    # Word colle le paragraphe suivant au tableau sans ce separateur.
    out.append("<w:p/>")
    return "".join(out)


# ------------------------------------------------------------- analyse du .md
#: Une ligne de liste EXIGE une espace après son marqueur. Sans ce détail, tout
#: paragraphe commençant par `**gras**` était pris pour une liste, puis écarté :
#: 317 lignes sur 2490 disparaissaient EN SILENCE, dont tous les encadrés
#: « Piège » et « À faire » du manuel. Constaté le 2026-09-07, et c'est
#: exactement le mode de défaillance que ce manuel enseigne à redouter.
LISTE = re.compile(r"^\s*([-*+]|\d+\.)\s+\S")


def _debut_de_bloc(ligne: str) -> bool:
    """La ligne ouvre-t-elle une construction que le paragraphe ne doit pas manger ?"""
    return (ligne.startswith(("#", "|", "```", ">"))
            or bool(LISTE.match(ligne))
            or bool(re.match(r"^---+$", ligne.strip())))


@dataclass
class Conversion:
    corps: list[str] = field(default_factory=list)
    titres: int = 0
    tableaux: int = 0
    blocs_code: int = 0
    #: Les lignes de source réellement consommées. Sert au contrôle de perte :
    #: sans lui, une ligne écartée par erreur ne se voit pas.
    lues: int = 0
    ignorees: list[tuple[int, str]] = field(default_factory=list)


def convertir(markdown: str) -> Conversion:
    c = Conversion()
    lignes = markdown.splitlines()
    i = 0
    while i < len(lignes):
        ligne = lignes[i]

        # Bloc de code encadré.
        if ligne.startswith("```"):
            i += 1
            dedans = 0
            while i < len(lignes) and not lignes[i].startswith("```"):
                c.corps.append(_ligne_code(lignes[i]))
                dedans += 1
                i += 1
            c.blocs_code += 1
            c.lues += dedans + 2
            c.corps.append("<w:p/>")
            i += 1
            continue

        # Tableau : une ligne de `|` suivie d'une ligne de séparation.
        if (ligne.startswith("|") and i + 1 < len(lignes)
                and re.match(r"^\|[\s:|-]+\|$", lignes[i + 1].strip())):
            brut = []
            while i < len(lignes) and lignes[i].startswith("|"):
                brut.append(lignes[i])
                i += 1
            cellules = [[x.strip() for x in ligne.strip().strip("|").split("|")]
                        for ligne in brut
                        if not re.match(r"^\|[\s:|-]+\|$", ligne.strip())]
            c.corps.append(_tableau(cellules))
            c.tableaux += 1
            c.lues += len(brut)
            continue

        # Titres.
        m = re.match(r"^(#{1,4})\s+(.*)$", ligne)
        if m:
            niveau = len(m.group(1))
            c.titres += 1
            c.lues += 1
            c.corps.append(_paragraphe(
                _texte_courant(m.group(2)), style=f"Titre{niveau}",
                saut_avant=(niveau == 1 and c.titres > 1),
                garder_avec_suivant=True))
            i += 1
            continue

        # Séparateur horizontal : ignoré, les titres suffisent à découper.
        if re.match(r"^---+$", ligne.strip()):
            i += 1
            continue

        # Citation.
        if ligne.startswith(">"):
            bloc = []
            while i < len(lignes) and lignes[i].startswith(">"):
                bloc.append(lignes[i].lstrip("> ").rstrip())
                i += 1
            c.corps.append(_paragraphe(_texte_courant(" ".join(bloc)),
                                       style="Citation"))
            c.lues += len(bloc)
            continue

        # Listes. Le marqueur doit etre suivi d'une espace ET d'un caractere :
        # `**gras**` n'est donc PAS une liste, ce qui etait le defaut.
        if LISTE.match(ligne):
            m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", ligne)
            style = "Puce" if m.group(1) in ("-", "*", "+") else "Numero"
            c.corps.append(_paragraphe(_texte_courant(m.group(2)), style=style))
            c.lues += 1
            i += 1
            continue

        # Paragraphe : on agrège les lignes jusqu'à une ligne vide ou jusqu'au
        # début d'une autre construction.
        if ligne.strip():
            bloc = []
            depart = i
            while (i < len(lignes) and lignes[i].strip()
                   and (i == depart or not _debut_de_bloc(lignes[i]))):
                bloc.append(lignes[i].strip())
                i += 1
            if bloc:
                c.corps.append(_paragraphe(_texte_courant(" ".join(bloc))))
                c.lues += len(bloc)
            else:
                # Ne devrait pas arriver : on le CONSIGNE au lieu de l'avaler.
                c.ignorees.append((depart + 1, ligne[:70]))
                i += 1
            continue
        i += 1
    return c


# ------------------------------------------------------------------- styles
def styles_xml() -> str:
    def titre(nom: str, taille: int, couleur: str, avant: int) -> str:
        return (f'<w:style w:type="paragraph" w:styleId="{nom}">'
                f'<w:name w:val="{nom}"/><w:basedOn w:val="Normal"/>'
                f'<w:pPr><w:keepNext/><w:spacing w:before="{avant}" '
                f'w:after="120"/></w:pPr>'
                f'<w:rPr><w:b/><w:color w:val="{couleur}"/>'
                f'<w:sz w:val="{taille * 2}"/></w:rPr></w:style>')

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{NS_W}">
  <w:docDefaults><w:rPrDefault><w:rPr>
    <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/>
  </w:rPr></w:rPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="140" w:line="276" w:lineRule="auto"/>
    <w:jc w:val="both"/></w:pPr>
  </w:style>
  {titre("Titre1", 22, BLEU, 360)}
  {titre("Titre2", 16, BLEU, 280)}
  {titre("Titre3", 13, GRIS, 220)}
  {titre("Titre4", 11, GRIS, 180)}
  <w:style w:type="paragraph" w:styleId="Code">
    <w:name w:val="Code"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
    <w:ind w:left="240"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
    <w:sz w:val="18"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Citation">
    <w:name w:val="Citation"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="360"/>
    <w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="BFBFBF"/>
    </w:pBdr></w:pPr>
    <w:rPr><w:i/><w:color w:val="{GRIS}"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Puce">
    <w:name w:val="Puce"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>
    <w:spacing w:after="60"/><w:jc w:val="left"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Numero">
    <w:name w:val="Numero"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>
    <w:spacing w:after="60"/><w:jc w:val="left"/></w:pPr>
  </w:style>
</w:styles>"""


def numbering_xml() -> str:
    """Les puces et la numérotation. Sans ce fichier, Word ignore `numPr`."""
    def definition(idx: int, format_: str, texte: str) -> str:
        return (f'<w:abstractNum w:abstractNumId="{idx}"><w:lvl w:ilvl="0">'
                f'<w:start w:val="1"/><w:numFmt w:val="{format_}"/>'
                f'<w:lvlText w:val="{texte}"/><w:lvlJc w:val="left"/>'
                '<w:pPr><w:ind w:left="420" w:hanging="240"/></w:pPr>'
                '</w:lvl></w:abstractNum>')

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{NS_W}">
  {definition(0, "bullet", "•")}
  {definition(1, "decimal", "%1.")}
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def ecrire(chemin: Path, corps: list[str], titre: str) -> None:
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document xmlns:w="{NS_W}"><w:body>'
                + "".join(corps)
                + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                  '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
                  'w:left="1134"/></w:sectPr></w:body></w:document>')

    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
             'content-types">'
             '<Default Extension="rels" ContentType="application/'
             'vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/'
             'vnd.openxmlformats-officedocument.wordprocessingml.document.'
             'main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/'
             'vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
             '<Override PartName="/word/numbering.xml" ContentType="application/'
             'vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
             '<Override PartName="/docProps/core.xml" ContentType="application/'
             'vnd.openxmlformats-package.core-properties+xml"/>'
             '</Types>')

    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '</Relationships>')

    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org'
                '/officeDocument/2006/relationships/styles" '
                'Target="styles.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org'
                '/officeDocument/2006/relationships/numbering" '
                'Target="numbering.xml"/>'
                '</Relationships>')

    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(titre)}</dc:title>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{maintenant}'
            '</dcterms:created></cp:coreProperties>')

    chemin.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles_xml())
        z.writestr("word/numbering.xml", numbering_xml())
        z.writestr("word/_rels/document.xml.rels", doc_rels)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.splitlines()[2].strip(), file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    if not source.exists():
        print(f"ERREUR : {source} introuvable.", file=sys.stderr)
        return 2
    texte = source.read_text(encoding="utf-8")
    conversion = convertir(texte)

    premier = next((x[2:].strip() for x in texte.splitlines()
                    if x.startswith("# ")), source.stem)
    cible = (Path(sys.argv[2]) if len(sys.argv) > 2
             else source.with_suffix(".docx"))

    # CONTROLE DE PERTE, et il n est pas decoratif. Le 2026-09-07, un defaut
    # de ce script ecartait EN SILENCE tout paragraphe commencant par du gras :
    # 317 lignes sur 2490, dont tous les encadres « Piege » et « A faire ». Une
    # conversion qui perd du contenu sans le dire est pire qu une conversion qui
    # echoue. On compare donc les lignes non vides de la source aux lignes
    # reellement consommees, et on refuse d ecrire si l ecart est notable.
    utiles = sum(1 for x in texte.splitlines() if x.strip())
    manquantes = utiles - conversion.lues
    if conversion.ignorees:
        for numero, extrait in conversion.ignorees[:5]:
            print(f"  ligne {numero} ignoree : {extrait!r}", file=sys.stderr)
    if manquantes > utiles * 0.02:
        print(f"ECHEC : {manquantes} ligne(s) utile(s) sur {utiles} non "
              f"converties, soit {manquantes / utiles:.0%}. Rien n a ete ecrit.",
              file=sys.stderr)
        return 1

    ecrire(cible, conversion.corps, premier)
    taille = cible.stat().st_size
    print(f"{cible} ecrit, {taille / 1024:.0f} Ko")
    print(f"  {conversion.lues} lignes utiles converties sur {utiles}")
    print(f"  {conversion.titres} titres, {conversion.tableaux} tableaux, "
          f"{conversion.blocs_code} blocs de code")
    print(f"  {len(conversion.corps)} elements, "
          f"{len(texte.splitlines())} lignes de source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
