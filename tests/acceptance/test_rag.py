"""Acceptance — recherche documentaire (exigences DSI E1, E2, E6)."""

from __future__ import annotations

from tests.conftest import EVAL_DIR, call_tool


async def test_answer_question_cite_ses_sources():
    # E1 : une question couverte par le corpus reçoit une réponse sourcée
    # (titre + référence + date), via le tool de haut niveau.
    result = await call_tool(
        "support",
        "answer_question",
        {"question": "quelle est la procédure de retour d'un produit défectueux sous garantie ?"},
    )
    assert result["status"] == "ok"
    assert result["payload"]["answer"].strip()
    sources = result["payload"]["sources"]
    assert sources, "réponse sans source"
    for src in sources:
        assert src["titre"].strip()
        assert src["reference"].strip()
        assert src["date"].strip()


async def test_hors_corpus_signale_sans_inventer():
    # E1 : hors corpus, l'outil ne fabrique pas de réponse et le signale.
    result = await call_tool(
        "support",
        "answer_question",
        {"question": "quelle est la politique de télétravail chez Sorabel ?"},
    )
    assert result["status"] == "hors_corpus"
    assert result["message"].strip()
    assert not result["payload"].get("answer")


async def test_recherche_par_reference_exacte():
    # E2 : la recherche « REF-8842 » remonte la fiche technique correspondante
    # en tête des résultats.
    result = await call_tool("support", "search_docs", {"query": "REF-8842"})
    assert result["status"] == "ok"
    hits = result["payload"]["hits"]
    assert hits
    top = hits[0]
    assert top["metadata"]["reference"] == "REF-8842"
    assert top["metadata"]["doc_type"] == "fiche_technique"


def test_gain_hybride_mesure_et_documente(questions_rag):
    # E6 : comparée à la recherche dense initiale sur questions_rag.jsonl,
    # la recherche hybride donne un gain mesuré et documenté
    # (rapport chiffré attendu dans eval/rapport_gain.md).
    exact = [q for q in questions_rag if q["type"] == "reference_exacte"]
    assert exact, "le jeu d'éval doit contenir des questions par référence exacte"

    rapport = EVAL_DIR / "rapport_gain.md"
    assert rapport.exists(), "rapport de mesure absent : eval/rapport_gain.md"
    text = rapport.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "dense" in lowered
    assert "hybride" in lowered or "hybrid" in lowered
    assert "reference_exacte" in lowered or "référence exacte" in lowered
    assert any(ch.isdigit() for ch in text), "le rapport doit être chiffré"
