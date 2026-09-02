"""Quatre formats vers le Document canonique.

RÈGLE, posée au chantier 1 après la revue : **aucune expression régulière maison
sur un flux PDF**. L'outil de relevé du dépôt en portait une, dont la classe de
caractères s'arrêtait à la première parenthèse échappée : le titre
`FICHE TECHNIQUE - Cheville métallique M8 \\(boîte 100\\)` était jeté en entier,
et avec lui 47 titres de fiche sur 150. On passe par `pypdf`, qui décode le
format au lieu de le deviner.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .document import MOTIF_REF, Document

# --- Motifs des en-têtes PDF -------------------------------------------------
# Ils décrivent le gabarit réel du corpus, relevé fichier en main.
TITRE_FICHE = re.compile(r"^FICHE TECHNIQUE\s*-\s*(.+)$", re.M)
TITRE_NOTICE = re.compile(r"^NOTICE D'INSTALLATION\s*-\s*(.+)$", re.M)
CHAMP_VERSION = re.compile(r"Version\s*:\s*([\d.]+)")
CHAMP_DATE = re.compile(r"Date\s*:\s*(\d{4}-\d{2}-\d{2})")
SECTION_NUMEROTEE = re.compile(r"^(\d+)\.\s+(.+)$", re.M)

# --- Motifs des noms de fichier ----------------------------------------------
NOM_FICHE = re.compile(r"^(REF-\d{4})-v([\d.]+)$")
NOM_NOTICE = re.compile(r"^notice-(REF-\d{4})-v([\d.]+)$")
NOM_SAV = re.compile(r"^(proc-.+?)-v([\d.]+)$")


class ErreurChargement(RuntimeError):
    """Un document qu'on ne sait pas lire arrête l'ingestion.

    On ne l'ignore pas en silence : un document manquant à l'index ne produit
    aucune erreur à la recherche, il produit une réponse incomplète, ce qui est
    strictement pire.
    """


def _exige(valeur: str | None, quoi: str, chemin: Path) -> str:
    if not valeur or not valeur.strip():
        raise ErreurChargement(f"{chemin.name} : {quoi} absent ou vide")
    return valeur.strip()


def _texte_pdf(chemin: Path) -> str:
    pages = [page.extract_text() or "" for page in PdfReader(str(chemin)).pages]
    return "\n".join(pages)


def charger_fiche(chemin: Path) -> Document:
    """Fiche technique : une page dense, un seul chunk. Le document EST la section."""
    nom = NOM_FICHE.match(chemin.stem)
    if not nom:
        raise ErreurChargement(f"{chemin.name} : nom hors gabarit REF-XXXX-vX.Y")
    reference, version = nom.group(1), nom.group(2)

    texte = _texte_pdf(chemin)
    titre = _exige(m.group(1) if (m := TITRE_FICHE.search(texte)) else None, "titre", chemin)
    date = _exige(m.group(1) if (m := CHAMP_DATE.search(texte)) else None, "date", chemin)

    return Document(
        doc_id=chemin.stem,
        doc_type="fiche_technique",
        titre=titre,
        reference=reference,
        version=version,
        date=date,
        version_group=reference,
        texte=texte,
        sections=[("", texte)],
        source=f"fiches/{chemin.name}",
    )


def charger_notice(chemin: Path) -> Document:
    """Notice : des sections numérotées, une par étape d'installation.

    Une question vise une étape précise (« que vérifier 48 h après la mise en
    service ? »), pas la notice entière : le chunk par section rend le passage
    cité exactement aussi précis que la question.
    """
    nom = NOM_NOTICE.match(chemin.stem)
    if not nom:
        raise ErreurChargement(f"{chemin.name} : nom hors gabarit notice-REF-XXXX-vX.Y")
    reference, version = nom.group(1), nom.group(2)

    texte = _texte_pdf(chemin)
    titre = _exige(m.group(1) if (m := TITRE_NOTICE.search(texte)) else None, "titre", chemin)
    date = _exige(m.group(1) if (m := CHAMP_DATE.search(texte)) else None, "date", chemin)

    # Découpe sur les têtes de section : le corps d'une section va jusqu'à la
    # suivante, et la queue du document reste attachée à la dernière.
    debuts = list(SECTION_NUMEROTEE.finditer(texte))
    sections: list[tuple[str, str]] = []
    for i, tete in enumerate(debuts):
        fin = debuts[i + 1].start() if i + 1 < len(debuts) else len(texte)
        corps = texte[tete.end():fin].strip()
        sections.append((f"{tete.group(1)}. {tete.group(2).strip()}", corps))
    if not sections:
        raise ErreurChargement(f"{chemin.name} : aucune section numerotee trouvee")

    return Document(
        doc_id=chemin.stem,
        doc_type="notice",
        titre=titre,
        reference=reference,
        version=version,
        date=date,
        version_group=f"notice-{reference}",
        texte=texte,
        sections=sections,
        source=f"notices/{chemin.name}",
    )


def charger_sav(chemin: Path) -> Document:
    """Procédure SAV : HTML, métadonnées dans les balises `meta`.

    Piège déjà corrigé au dossier : la forme réelle est
    `<meta name="version" content="...">`, et non `<meta version="...">`.

    Une procédure ne porte PAS de référence produit : elle s'applique à tout le
    catalogue. Son identifiant propre tient donc lieu de `reference`, car E1
    exige une référence non vide dans toute source citée.
    """
    nom = NOM_SAV.match(chemin.stem)
    if not nom:
        raise ErreurChargement(f"{chemin.name} : nom hors gabarit proc-<code>-vX.Y")
    code, version = nom.group(1), nom.group(2)

    soupe = BeautifulSoup(chemin.read_text(encoding="utf-8"), "html.parser")

    def meta(champ: str) -> str | None:
        balise = soupe.find("meta", attrs={"name": champ})
        return balise.get("content") if balise else None

    h1 = soupe.find("h1")
    titre = _exige(h1.get_text(strip=True) if h1 else None, "titre h1", chemin)
    date = _exige(meta("date"), "meta date", chemin)
    version = _exige(meta("version") or version, "meta version", chemin)

    declare = meta("type")
    if declare and declare != "procedure_sav":
        raise ErreurChargement(f"{chemin.name} : doc_type declare {declare!r}, attendu procedure_sav")

    # Découpe sur les h2 : chaque section est un bloc de sens autonome.
    sections: list[tuple[str, str]] = []
    corps_intro = []
    for element in h1.find_next_siblings():
        if element.name == "h2":
            break
        corps_intro.append(element.get_text(" ", strip=True))
    if intro := " ".join(corps_intro).strip():
        sections.append(("Objet", intro))
    for tete in soupe.find_all("h2"):
        morceaux = []
        for element in tete.find_next_siblings():
            if element.name == "h2":
                break
            morceaux.append(element.get_text(" ", strip=True))
        sections.append((tete.get_text(strip=True), " ".join(morceaux).strip()))
    if not sections:
        raise ErreurChargement(f"{chemin.name} : aucune section")

    return Document(
        doc_id=chemin.stem,
        doc_type="procedure_sav",
        titre=titre,
        reference=code.upper(),
        version=version,
        date=date,
        version_group=code,
        texte=soupe.get_text("\n", strip=True),
        sections=sections,
        source=f"sav/{chemin.name}",
    )


def charger_note(chemin: Path) -> Document:
    """Note interne : Markdown avec en-tête YAML. Très court, un seul chunk.

    Comme la procédure SAV, une note ne porte pas de référence produit ; son
    identifiant de fichier en tient lieu. Certaines citent une référence dans
    leur corps, on la préfère quand elle existe.
    """
    brut = chemin.read_text(encoding="utf-8")
    separe = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", brut, re.S)
    if not separe:
        raise ErreurChargement(f"{chemin.name} : en-tete YAML absent")
    entete, corps = separe.group(1), separe.group(2).strip()

    champs = dict(
        re.findall(r"^(\w+)\s*:\s*'?\"?(.*?)'?\"?\s*$", entete, re.M)
    )
    titre = _exige(champs.get("titre"), "titre", chemin)
    date = _exige(champs.get("date"), "date", chemin)
    version = champs.get("version") or "1.0"

    declare = champs.get("type")
    if declare and declare != "note_interne":
        raise ErreurChargement(f"{chemin.name} : doc_type declare {declare!r}, attendu note_interne")

    trouvee = MOTIF_REF.search(corps)
    reference = trouvee.group(0).upper() if trouvee else chemin.stem.upper()

    return Document(
        doc_id=chemin.stem,
        doc_type="note_interne",
        titre=titre,
        reference=reference,
        version=version,
        date=date,
        version_group=chemin.stem,
        texte=corps,
        sections=[("", corps)],
        source=f"notes/{chemin.name}",
    )


#: Le dossier d'origine décide du loader. La correspondance dossier vers
#: doc_type est contrôlée contre `governance/matrice.yaml`, pas devinée ici.
LOADERS = {
    "fiches": charger_fiche,
    "notices": charger_notice,
    "sav": charger_sav,
    "notes": charger_note,
}
EXTENSIONS = {"fiches": ".pdf", "notices": ".pdf", "sav": ".html", "notes": ".md"}


def charger_corpus(racine: Path) -> list[Document]:
    """Charge les quatre collections. Un seul document illisible arrête tout."""
    documents: list[Document] = []
    for dossier, loader in LOADERS.items():
        chemin = racine / dossier
        if not chemin.is_dir():
            raise ErreurChargement(f"dossier de corpus absent : {chemin}")
        for fichier in sorted(chemin.glob(f"*{EXTENSIONS[dossier]}")):
            documents.append(loader(fichier))
    return documents
