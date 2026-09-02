# Carte de la pile technique

> Vue consolidée, **à titre informatif**, de ce qui est retenu et de ce qui est
> écarté. Elle ne décide rien : chaque ligne renvoie à la décision qui fait foi,
> dispersée aujourd'hui entre les chantiers 1, 2, 6 et 7.
>
> Elle existe pour répondre en un coup d'œil à deux questions que le dossier
> obligeait à reconstituer : *avec quoi construit-on ?* et surtout *pourquoi
> pas autre chose ?*

---

## 1. Ce qui est retenu

| Rôle | Retenu | Décision | Motif en une ligne |
| --- | --- | --- | --- |
| Langage | Python 3.11 ou plus | *proposé* | Seul écosystème où le SDK MCP, `sqlglot` et les modèles cohabitent |
| Framework MCP | FastMCP, le SDK Python officiel | *proposé* | Implémentation de référence du protocole, pas une surcouche |
| Base métier | SQLite, lecture seule au niveau du pilote | D31 | Les données sont relationnelles, et E3 exige un SQL analysable par AST |
| Store vectoriel | Chroma, embarqué | D32 | Filtre par métadonnée **avant** la recherche |
| Index lexical | BM25 applicatif, séparé du store | D32, P3 | Rend la baseline dense isolable, ce dont E6 dépend |
| Fusion | RRF, k = 60 | D5 | Fusionne des rangs, donc insensible à des scores non comparables |
| Embeddings | `bge-m3` | P2 | Multilingue, bon en français. 568 M paramètres, donc *présumé* tenir sur processeur : à mesurer, ce n'est pas un fait sourcé |
| Reranking | `bge-reranker-v2-m3` | P2 | Cross-encoder, lit question et passage ensemble |
| Génération SQL | modèle coder instruct | P5, D36 | Seul composant exigeant un accélérateur ou une API |
| Validation SQL | `sqlglot`, analyse AST | D11 | Raisonne sur la structure réelle, pas sur des mots interdits |
| Identité | variable d'environnement au lancement | D28 | Le protocole ne fournit rien de vérifiable en transport local |
| Matrice d'accès | fichier YAML déclaratif | D21 | Source de vérité **unique** des droits |
| Journal | fichier JSONL en ajout | D33 | Une ligne complète par appel, lisible sans outil |
| Persistance | chemin unique `SORABEL_DATA_DIR` | D35 | Le stockage de conteneur est éphémère par défaut |
| Hébergement | Azure, stratégie incrémentale | D37 | Le brief exige un lien vers une interface déployée |
| Client support | application Slack, réponse différée | D34 | Le budget de 3 secondes de Slack interdit la réponse directe |

## 2. Ce qui est écarté, et pourquoi

C'est la moitié la plus utile de ce document. Un choix ne se justifie pas par ses
qualités, mais par ce qu'il évite.

| Écarté | Envisagé pour | Motif du rejet | Décision |
| --- | --- | --- | --- |
| **PostgreSQL** | base métier | Ses rôles permettraient un droit par colonne, mais cela **encoderait la matrice une seconde fois**, contre D21 | D31 |
| **FAISS** | store vectoriel | C'est une bibliothèque de similarité, pas une base : **elle ne filtre pas par métadonnée**. E2 et E4 seraient à recoder | D32 |
| **Qdrant** | store vectoriel | Son hybride natif rend la **baseline dense moins nette à isoler**, or E6 en dépend. Et c'est un service à administrer | D32 |
| **sqlite-vec** | store vectoriel | Unifierait la technologie, mais écosystème plus jeune et gain non décisif. Non retenu **par prudence**, pas par rejet | D32 |
| **Azure AI Search** | store vectoriel | **Pas** une impossibilité technique, le vecteur pur y est documenté. Mesurer l'hybride dans le service qui le vend affaiblit la neutralité de la mesure | 07 §5.2 |
| **Entra ID** | identité | La spécification MCP exige les indicateurs de ressource RFC 8707. **Absence de preuve**, non preuve d'absence : aucune source officielle ne revendique la conformité. En revanche Microsoft documente noir sur blanc l'absence d'enregistrement dynamique de client | 07 §5.1 |
| **Keycloak** | identité | **Même limite qu'Entra ID** : « cannot currently recognize the resource parameter ». Ajoute un service et une base pour ne rien résoudre | 07 §5.1 bis |
| **Base pour le journal** | journalisation | Écriture seule, relu après coup : un fichier suffit, et se lit sans outil en démonstration | D33 |
| **Documentaire, clé-valeur, graphe, colonne** | base métier | Aucun ne fournit un langage de requête analysable par AST, ce dont E3 dépend | D31 |

## 3. Le fil rouge des rejets

Trois motifs reviennent, et il vaut la peine de les nommer parce qu'ils
resserviront à chaque nouveau choix.

**Une seule source de vérité pour les droits.** C'est ce qui écarte PostgreSQL et
c'est ce qui interdirait d'utiliser le moteur de politiques de Keycloak.
Dupliquer un **invariant** est sain, ainsi la connexion en lecture seule qui
énonce « aucune écriture, jamais » ; dupliquer une **configuration qui change**
crée la dérive.

**La mesure doit rester attribuable.** C'est ce qui écarte Qdrant et Azure AI
Search. Non parce qu'une baseline dense y serait impossible, elle ne l'est pas,
mais parce que composer nous-mêmes deux index séparés rend l'ablation lisible
brique par brique : dense seul, puis hybride, puis reranking. E6 exige que le
gain soit imputable à un choix nommé, pas à un moteur qui fait tout.

Ce motif a été corrigé le 2026-09-02, après vérification de la documentation
officielle. C'est la deuxième fois que ce dossier écrit un motif faux sous une
conclusion juste, après celui de P3. Un motif faux ne se voit pas à l'usage : il
ne tombe que devant un jury.

**La gouvernance ne se recode pas à la main.** C'est ce qui écarte FAISS : le
filtrage par métadonnée n'est pas un détail de performance, c'est le mécanisme
par lequel E2 et E4 tiennent.

## 4. Ce qui reste ouvert

| Sujet | État |
| --- | --- |
| Modèle exact pour la génération SQL | Ordre d'essai fixé par D36 : petit modèle sur processeur, mesure sur SQL-01 à 12, puis GPU, puis API |
| Plateforme d'hébergement précise | App Service ou Container Apps. D35 rend le choix indolore, la persistance passe par une seule variable |
| Région et carte GPU, si la génération SQL en exige une | L'A100 n'existe pas en Europe de l'Ouest stricte, seulement à Sweden Central. À trancher avant le lot 5 |
| Framework de l'interface graphique | Non tranché. N'engage aucune autre décision |
| Coût mensuel | Non chiffré, item A4 du backlog. Le palier gratuit de Container Apps est confirmé, les tarifs des modèles restent à relever |

## 5. Où sont les droits, et où ils ne sont pas

La pile technique et la matrice d'accès sont deux choses distinctes, et les
confondre est le piège que ce document doit aider à éviter.

```
governance/matrice.yaml          QUI a droit a QUOI. Source de verite unique.
governance/matrice_lisible.md    la meme chose, generee, a titre informatif.
ce document                      AVEC QUOI on construit. Aucun droit ici.
```

Aucun composant de la pile ne décide des droits. Ni la base, ni le store, ni le
fournisseur d'identité s'il en arrive un. Un fournisseur d'identité dit **qui**,
la matrice dit **quoi**.
