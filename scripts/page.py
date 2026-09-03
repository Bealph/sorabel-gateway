"""Réglage de page, tolérant au mode multipage.

`st.set_page_config` ne peut être appelé qu'**une fois par exécution**. Or les
trois pages de démonstration servent dans deux modes :

- seules, `streamlit run scripts/demo_mcp.py`, et elles doivent alors régler
  elles-mêmes leur titre et leur largeur ;
- assemblées par `app.py`, où l'entrée a déjà réglé la page avant de lancer
  la page choisie.

Sans cette précaution, le second appel lève une exception et l'application
déployée tombe alors que chaque page marche isolément. C'est exactement le
genre de défaut qui n'apparaît qu'après l'assemblage.
"""
from __future__ import annotations

import streamlit as st


def configurer(titre: str) -> None:
    """Règle la page si personne ne l'a déjà fait, sans jamais échouer."""
    try:
        st.set_page_config(page_title=titre, layout="wide")
    except Exception:  # noqa: BLE001
        # `StreamlitAPIException` quand l'entrée multipage a déjà réglé la
        # page. C'est le cas nominal sous `app.py`, pas une anomalie.
        pass
