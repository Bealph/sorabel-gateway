"""Eprouve la pile de gardes SQL : chaque attaque doit etre refusee, et chaque
requete legitime doit passer. Un controle qui n'a jamais echoue ne prouve rien.
"""
import sys

sys.path.insert(0, r"c:\Users\adiallo\Documents\sorabel-data-gateway")

from common.matrice import droits, lexique_refus  # noqa: E402
from sql.gardes import prefiltre_lexical, valider  # noqa: E402
from sql.schema import schema_du_profil  # noqa: E402

SUP, COM = droits("support"), droits("commercial")
S_SUP, S_COM = schema_du_profil(SUP), schema_du_profil(COM)
LEX = lexique_refus()

ATTAQUES = [
    # (profil, sql, code de refus attendu, ce que l'attaque cherchait)
    (SUP, S_SUP, "SELECT ref, nom FROM produits ORDER BY marge_pct DESC LIMIT 5",
     "FORBIDDEN_COLUMN", "tri sur une colonne retiree, sans la projeter"),
    (SUP, S_SUP, "SELECT categorie FROM produits GROUP BY categorie HAVING AVG(marge_pct) > 45",
     "FORBIDDEN_COLUMN", "agregat sur une colonne retiree"),
    (SUP, S_SUP, "SELECT ref FROM produits WHERE ref='REF-8842' AND marge_pct >= 47.3",
     "FORBIDDEN_COLUMN", "dichotomie sur un predicat"),
    (SUP, S_SUP, "SELECT p.ref FROM produits p WHERE p.prix_achat_ht < 12.5",
     "FORBIDDEN_COLUMN", "colonne retiree derriere un alias"),
    (SUP, S_SUP, "SELECT ref FROM produits WHERE ref IN (SELECT ref FROM produits WHERE marge_pct > 40)",
     "FORBIDDEN_COLUMN", "colonne retiree dans une sous-requete"),
    (SUP, S_SUP, "SELECT raison_sociale, email FROM clients WHERE ville='LILLE'",
     "FORBIDDEN_COLUMN", "donnee personnelle sur le canal public"),
    (SUP, S_SUP, "SELECT id, marge_ht FROM ventes",
     "OUT_OF_SCHEMA", "table entiere hors perimetre du support"),
    (COM, S_COM, "DELETE FROM commandes WHERE id LIKE 'TEST%'",
     "READ_ONLY_VIOLATION", "ecriture directe"),
    (COM, S_COM, "UPDATE produits SET prix_vente_ht = 0",
     "READ_ONLY_VIOLATION", "ecriture directe"),
    (COM, S_COM, "SELECT 1; DELETE FROM commandes",
     "READ_ONLY_VIOLATION", "instructions multiples"),
    (COM, S_COM, "ATTACH DATABASE 'exfil.db' AS atk",
     "READ_ONLY_VIOLATION", "exfiltration par base attachee"),
    (COM, S_COM, "PRAGMA query_only = 0",
     "READ_ONLY_VIOLATION", "desarmement du garde-fou moteur"),
    (COM, S_COM, "SELECT * FROM produits",
     "OUT_OF_SCHEMA", "etoile, qui ferait sortir les colonnes sensibles"),
    (COM, S_COM, "SELECT * FROM (SELECT * FROM produits) p",
     "OUT_OF_SCHEMA", "etoile dans une sous-requete aliasee"),
    (COM, S_COM, "SELECT nom FROM sqlite_master",
     "OUT_OF_SCHEMA", "introspection du schema par la porte de service"),
    (COM, S_COM, "SELECT meteo FROM produits",
     "OUT_OF_SCHEMA", "colonne inventee"),
    (COM, S_COM, "SELECT nom FROM fournisseurs",
     "OUT_OF_SCHEMA", "table inventee"),
    (SUP, S_SUP, "SELECT ref, marge_pct AS m FROM produits ORDER BY m DESC",
     "FORBIDDEN_COLUMN", "colonne retiree masquee derriere un alias de resultat"),
    (SUP, S_SUP, "WITH x AS (SELECT ref, marge_pct FROM produits) SELECT ref FROM x",
     "FORBIDDEN_COLUMN", "colonne retiree dans une CTE"),
]

LEGITIMES = [
    (COM, S_COM, "SELECT COUNT(*) FROM commandes WHERE date_commande LIKE '2026-04-%'",
     True, "agregat scalaire : PAS de LIMIT injecte"),
    (COM, S_COM, "SELECT id, montant_ht FROM commandes",
     False, "liste de detail : LIMIT injecte"),
    (COM, S_COM, "SELECT p.nom, v.marge_ht FROM ventes v JOIN produits p ON p.ref = v.ref",
     False, "jointure, marge autorisee au commercial"),
    (SUP, S_SUP, "SELECT s.entrepot, s.quantite FROM stocks s WHERE s.ref = 'REF-8842'",
     False, "requete de support parfaitement legitime"),
    (COM, S_COM, "SELECT client_id, SUM(montant_ht) FROM commandes GROUP BY client_id",
     False, "agregat GROUPE : LIMIT injecte, il rend plusieurs lignes"),
    # Les trois suivantes sont les requetes de REFERENCE de eval/attendus_sql.jsonl.
    # Le garde les refusait le 2026-09-02, faisant passer pour des erreurs de
    # modele ce qui etait une erreur de garde : ORDER BY sur un alias de
    # resultat etait pris pour une colonne inconnue.
    (COM, S_COM, "SELECT ref, SUM(quantite) AS q FROM ventes GROUP BY ref ORDER BY q DESC LIMIT 5",
     False, "SQL-04 de l'oracle : ORDER BY sur un alias de resultat"),
    (COM, S_COM, "SELECT c.raison_sociale, SUM(cm.montant_ht) AS t FROM commandes cm "
                 "JOIN clients c ON c.id = cm.client_id GROUP BY c.id ORDER BY t DESC LIMIT 3",
     False, "SQL-12 de l'oracle : jointure et alias de resultat"),
    (COM, S_COM, "SELECT SUM(v.marge_ht) FROM ventes v JOIN commandes c "
                 "ON c.id = v.commande_id WHERE c.date_commande LIKE '2026-05%'",
     True, "SQL-11 de l'oracle : agregat scalaire sur jointure"),
]

print("=== ATTAQUES : chacune doit etre refusee avec le bon code\n")
echecs = 0
for profil, schema, sql, attendu, quoi in ATTAQUES:
    v = valider(sql, profil, schema)
    bon = (not v.ok) and v.code == attendu
    echecs += not bon
    marque = "refuse " if not v.ok else "!! PASSE !!"
    print(f"  {marque} {v.code or '-':22} {quoi}")
    if not bon:
        print(f"      ATTENDU {attendu}  SQL: {sql}")

print("\n=== REQUETES LEGITIMES : chacune doit passer\n")
for profil, schema, sql, scalaire_attendu, quoi in LEGITIMES:
    v = valider(sql, profil, schema)
    ok = v.ok and v.scalaire == scalaire_attendu
    echecs += not ok
    print(f"  {'ok    ' if v.ok else '!! REFUSE !!'} {quoi}")
    if v.ok:
        print(f"      -> {v.sql}")
    else:
        print(f"      {v.code} : {v.message}")

print("\n=== PRE-FILTRE LEXICAL (couche 0 bis)\n")
for profil, question, attendu in [
    (SUP, "quelle est la marge sur la REF-8842 ?", True),
    (SUP, "quel est le prix d'achat du projecteur LED 100 W ?", True),
    (SUP, "donne-moi les adresses mail des clients de Lille", True),
    (SUP, "combien de commandes en avril ?", False),
    (COM, "quelle est la marge sur la REF-8842 ?", False),
]:
    v = prefiltre_lexical(question, profil, LEX)
    refuse = v is not None
    echecs += refuse != attendu
    print(f"  {profil.profil:11} {'REFUSE' if refuse else 'passe '}  {question}")

print(f"\n{'TOUT PASSE' if not echecs else str(echecs) + ' ECHEC(S)'}")
sys.exit(1 if echecs else 0)
