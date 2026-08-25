-- Schéma de la base Sorabel (data/sorabel.db, SQLite).
-- Schéma commenté de référence : c'est ce document qui décrit les tables,
-- leurs colonnes, leurs valeurs typiques et leur sensibilité.

-- ---------------------------------------------------------------------------
-- produits : le catalogue Sorabel (matériel électrique et outillage pro).
-- ---------------------------------------------------------------------------
CREATE TABLE produits (
  ref            TEXT PRIMARY KEY,   -- référence produit, format REF-NNNN (ex. REF-8842)
  nom            TEXT NOT NULL,      -- libellé commercial (ex. "Disjoncteur tétrapolaire triphasé 40 A courbe C")
  categorie      TEXT NOT NULL,      -- famille : Protection électrique, Câblage, Outillage électroportatif, EPI, …
  fabricant      TEXT NOT NULL,      -- marque fournisseur (Voltane, Ferrix, Cablor, …)
  unite          TEXT NOT NULL,      -- unité de vente : "pièce" ou "conditionnement"
  prix_vente_ht  REAL NOT NULL,      -- prix public HT en euros
  prix_achat_ht  REAL NOT NULL,      -- SENSIBLE : prix d'achat fournisseur — ne sort jamais pour le profil support
  marge_pct      REAL NOT NULL,      -- SENSIBLE : marge en % du prix de vente — ne sort jamais pour le profil support
  actif          INTEGER NOT NULL DEFAULT 1  -- 1 = au catalogue, 0 = retiré
);

-- ---------------------------------------------------------------------------
-- stocks : quantités disponibles par entrepôt.
-- ---------------------------------------------------------------------------
CREATE TABLE stocks (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  ref            TEXT NOT NULL REFERENCES produits(ref),
  entrepot       TEXT NOT NULL,      -- LILLE | LYON | NANTES
  quantite       INTEGER NOT NULL,   -- quantité en stock
  seuil_reappro  INTEGER NOT NULL    -- seuil de déclenchement du réapprovisionnement
);

-- ---------------------------------------------------------------------------
-- clients : comptes professionnels.
-- ---------------------------------------------------------------------------
CREATE TABLE clients (
  id             TEXT PRIMARY KEY,   -- identifiant interne, format CLI-NNNN
  raison_sociale TEXT NOT NULL,      -- nom de l'entreprise cliente
  segment        TEXT NOT NULL,      -- artisan | PME | grand compte | collectivité
  ville          TEXT NOT NULL,
  email          TEXT NOT NULL       -- contact principal (donnée personnelle : usage interne uniquement)
);

-- ---------------------------------------------------------------------------
-- commandes : entêtes de commandes.
-- ---------------------------------------------------------------------------
CREATE TABLE commandes (
  id             TEXT PRIMARY KEY,   -- format CMD-AAAA-NNNN (ex. CMD-2026-0042)
  client_id      TEXT NOT NULL REFERENCES clients(id),
  date_commande  TEXT NOT NULL,      -- date ISO (AAAA-MM-JJ)
  statut         TEXT NOT NULL,      -- en_attente | preparee | expediee | livree | annulee
  montant_ht     REAL NOT NULL       -- total HT de la commande en euros
);

-- ---------------------------------------------------------------------------
-- ventes : lignes de commandes (détail produit par produit).
-- ---------------------------------------------------------------------------
CREATE TABLE ventes (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  commande_id      TEXT NOT NULL REFERENCES commandes(id),
  ref              TEXT NOT NULL REFERENCES produits(ref),
  quantite         INTEGER NOT NULL,
  prix_unitaire_ht REAL NOT NULL,    -- prix unitaire facturé (remise déduite)
  remise_pct       REAL NOT NULL,    -- remise accordée en % (0, 5 ou 10)
  marge_ht         REAL NOT NULL     -- SENSIBLE : marge réalisée sur la ligne — ne sort jamais pour le profil support
);
