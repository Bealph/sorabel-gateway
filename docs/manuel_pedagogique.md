# Manuel de construction : Sorabel Data Gateway

> Ce manuel vous permet de reconstruire seul un projet identique, sans aide.
> Il couvre tout : le raisonnement, les choix, les pièges, les mesures et le
> déploiement. Il est écrit pour être lu dans l'ordre la première fois, puis
> consulté par chapitre.
>
> Chaque fois qu'un choix a été payé par une erreur réelle, l'erreur est
> racontée. C'est la partie la plus utile : les bonnes décisions se devinent,
> les pièges non.

## Comment lire ce manuel

Le manuel suit l'ordre dans lequel il faut construire, et non l'ordre dans
lequel on présente. Vous pouvez donc l'utiliser comme un plan de travail.

Trois pictogrammes reviennent, sous forme de mots :

**À faire** annonce une action concrète, avec la commande.

**Piège** annonce une erreur que j'ai réellement commise ou rencontrée. Lisez
ces passages même si vous êtes pressé : ils font gagner des heures.

**Pourquoi** explique un choix. Un projet où l'on sait *pourquoi* se répare ;
un projet où l'on sait seulement *comment* se réécrit.

---

# 1. Ce que vous allez construire

## 1.1 L'histoire du client

Sorabel est un distributeur d'équipement électrique et d'outillage pour
professionnels. Son savoir vit dans deux mondes qui ne se parlent pas.

D'un côté, des **documents** : fiches techniques de produits, notices de
montage, procédures du service après-vente, notes internes. Quatre cents
fichiers, en PDF, HTML et Markdown, avec plusieurs versions du même document.

De l'autre, une **base de données** : produits, stocks, commandes, ventes,
clients. Des chiffres, des dates, des montants.

Chaque équipe s'était bricolé son outil. Le bot de recherche du service client
trouvait mal : il rate les références exactes, confond les versions d'une
notice, répond à côté. Les commerciaux tapaient du SQL à la main, et l'un
d'entre eux a verrouillé la base de production un vendredi soir. Résultat : les
réponses divergent d'une équipe à l'autre, et personne ne sait laquelle croire.

La direction informatique gèle les bricolages et impose **un point d'accès
unique et gouverné**.

## 1.2 Ce que « gouverné » veut dire

C'est le mot le plus important du projet, et il est facile à sous-estimer.

Gouverné ne veut pas dire « qui répond bien ». Cela veut dire que **le système
décide, pour chaque appel, ce que celui qui demande a le droit de voir**, et
qu'il **garde une trace** de chaque décision.

Concrètement, la même question posée par deux personnes différentes doit donner
deux réponses différentes. Un agent du service client qui demande la marge sur
un produit doit se voir **refuser**. Un commercial qui pose la même question
doit obtenir la réponse. Et les deux décisions doivent figurer dans un journal.

**Pourquoi c'est le cœur du projet.** Un moteur de recherche qui répond bien est
un exercice classique. Un moteur qui répond bien **et différemment selon qui
demande**, en le prouvant, est un produit. Si vous ne retenez qu'une chose de ce
manuel : le produit de Sorabel n'est pas la recherche, ce sont **les droits sur
la recherche**.

## 1.3 Les trois briques

```
                 +---------------------------+
                 |   La porte d'entree       |
                 |   un serveur unique       |
                 +---------------------------+
                    |          |          |
          +---------+     +----+----+     +--------+
          |               |         |              |
   Recherche dans   Interrogation   Gouvernance et journal
   les documents    de la base
```

**Brique 1, la recherche documentaire.** Retrouver le bon passage dans quatre
cents fichiers, et **citer sa source** : titre, référence, date. Si le corpus
n'a pas la réponse, le dire au lieu d'inventer.

**Brique 2, l'interrogation de la base.** Traduire une question en français vers
une requête SQL, **en lecture seule**, et renvoyer la requête avec le résultat.

**Brique 3, la gouvernance.** Une table de droits par profil, appliquée à tous
les niveaux, et un journal de tout appel, autorisé comme refusé.

## 1.4 Les six exigences

Ce sont les six lignes du contrat. Elles ne se négocient pas, et tout le projet
s'organise autour d'elles. Retenez-les par leur numéro, vous les citerez souvent.

| | L'exigence, en clair |
| --- | --- |
| **E1** | Toute réponse documentaire cite ses sources : titre, référence, date. Si le corpus ne couvre pas la question, l'outil **le dit** au lieu d'inventer. |
| **E2** | La recherche trouve aussi bien par référence exacte (« REF-8842 ») que par question en langage naturel (« quel disjoncteur pour du triphasé ? »). |
| **E3** | Tout SQL exécuté est en **lecture seule**, restreint aux tables autorisées du profil, et la requête générée est **toujours renvoyée** avec le résultat. |
| **E4** | Un **même serveur** sert tous les clients ; chaque client n'accède qu'aux outils, collections et tables prévus par la table de droits. |
| **E5** | **Tout appel**, autorisé ou refusé, est journalisé. Les colonnes sensibles (prix d'achat, marges) ne sortent **jamais** pour le profil support. |
| **E6** | Le **gain** de la recherche avancée sur la recherche simple est mesuré et documenté. Preuve chiffrée. |

**Piège d'interprétation, et il coûte cher.** E1 dit « cite ses sources ». On
peut satisfaire cette phrase à la lettre tout en citant **la mauvaise source** :
il suffit que le format soit correct. Nous verrons au chapitre 6 que c'est
exactement ce qui arrive si l'on oublie une règle d'une ligne. Une exigence
formellement satisfaite et factuellement fausse est le pire des résultats,
parce que rien ne la signale.

## 1.5 Les deux profils

Il n'y en a que deux. C'est peu, et c'est suffisant pour tout démontrer.

| Profil | Qui c'est | Outils | Documents | Tables |
| --- | --- | --- | --- | --- |
| `support` | le bot du service client, tourné vers l'extérieur | 7 sur 8 | fiches, notices, procédures | 4 sur 5, **pas** les ventes |
| `commercial` | le poste d'un commercial | les 8 | les 4, **notes internes comprises** | les 5 |

Trois différences seulement, mais chacune démontre une chose :

- un **outil** en moins pour le support, ce qui prouve qu'un catalogue se borne ;
- une **collection de documents** fermée, les notes internes, ce qui prouve
  qu'un filtrage documentaire existe ;
- une **table** retirée en entier, les ventes, plus des **colonnes** retirées,
  les marges et les prix d'achat, ce qui prouve que la restriction descend
  jusqu'à la colonne.

---

# 2. Le vocabulaire, en mots simples

Ce chapitre n'est pas un glossaire à survoler. Chaque terme y est expliqué avec
ce qu'il fait *et* ce qu'il ne fait pas, parce que la plupart des erreurs de ce
projet viennent d'un terme mal compris.

## 2.1 Autour de la recherche documentaire

**Corpus.** L'ensemble des documents. Ici, quatre cents fichiers.

**Chunk, ou morceau.** Un document entier est trop long pour être comparé
utilement à une question. On le découpe donc en morceaux de quelques centaines
de mots. Chaque morceau est ce qu'on retrouve et ce qu'on cite.

**Embedding, ou vecteur.** Un modèle transforme un texte en une liste de
nombres, par exemple 384 nombres. Deux textes qui parlent de la même chose
donnent deux listes proches. « Proche » se mesure par un calcul simple, le
**cosinus**, qui vaut 1 pour deux textes identiques et 0 pour deux textes sans
rapport.

**Recherche dense.** On transforme la question en vecteur, on la compare aux
vecteurs de tous les morceaux, on garde les plus proches. Elle comprend le sens,
donc elle trouve « disjoncteur triphasé » quand le texte dit « protection sur
trois phases ».

**Ce qu'elle ne sait pas faire :** retrouver une référence exacte. Pour un
modèle de sens, « REF-8842 » et « REF-8843 » se ressemblent énormément, alors
que ce sont deux produits différents. C'est le défaut que E2 vise.

**BM25, ou recherche lexicale.** L'ancienne méthode, et elle reste excellente :
on compte les mots communs entre la question et le morceau, en donnant plus de
poids aux mots rares. « REF-8842 » est un mot rarissime, donc BM25 le trouve
parfaitement. En revanche BM25 ne comprend rien : si la question dit
« triphasé » et le texte « trois phases », il ne voit aucun lien.

**Recherche hybride.** Faire les deux, puis fusionner les deux classements.
C'est la réponse à E2 : le dense apporte le sens, le lexical apporte l'exactitude.

**RRF, fusion réciproque des rangs.** La façon de fusionner deux classements.
On n'additionne **pas** les scores, parce que les scores des deux méthodes ne
sont pas sur la même échelle : un cosinus vaut entre 0 et 1, un score BM25 peut
valoir 12 ou 40. On additionne des **rangs** : un document classé premier
rapporte 1/(60+1), classé deuxième 1/(60+2), et ainsi de suite. Le 60 est une
constante d'usage. Un document bien classé par les deux méthodes remonte, un
document bien classé par une seule remonte moins.

**Reranking, ou reclassement.** Les deux méthodes précédentes comparent la
question et le morceau **séparément** : chacun devient un vecteur, puis on
compare les vecteurs. Un modèle de reclassement, appelé **cross-encoder**, lit
la question et le morceau **ensemble** et rend une note. C'est beaucoup plus
lent, donc on ne l'applique qu'aux vingt ou trente meilleurs candidats, pour
les remettre dans le bon ordre.

**Abstention.** Décider de ne pas répondre. C'est la moitié de E1, et la moitié
qu'on oublie. Le système doit être capable de dire « la documentation ne couvre
pas cette question » plutôt que de rendre le morceau le moins mauvais.

## 2.2 Autour de la base de données

**Text-to-SQL.** Traduire une question en français vers une requête SQL.

**Lecture seule.** Aucune modification de la base. Ni écriture, ni suppression,
ni création de table. C'est E3, et nous verrons qu'une seule barrière ne suffit
pas.

**AST, arbre syntaxique.** Une requête SQL peut être analysée comme une phrase :
on obtient un arbre où chaque nœud est un élément de grammaire, un `SELECT`, un
`WHERE`, un nom de colonne. Analyser cet arbre est infiniment plus sûr que
chercher des mots interdits dans le texte de la requête. Un filtre textuel se
contourne par une majuscule, un commentaire ou un espace ; un arbre ne se
contourne pas, parce qu'il décrit ce que la requête **fait**.

**Colonne sensible.** Une colonne que certains profils ne doivent jamais voir.
Ici : prix d'achat, marge en pourcentage, marge en euros.

## 2.3 Autour du protocole

**MCP.** Un protocole standard qui permet à un programme d'exposer des
**outils** à un client. Le client demande la liste des outils, puis en appelle
un avec des arguments et reçoit une réponse. C'est un contrat de conversation,
rien de plus.

**Outil, ou tool.** Une fonction exposée par le serveur, avec un nom, des
arguments et une réponse. Nous en aurons huit.

**stdio.** Le mode de communication le plus simple : le client lance le serveur
comme un programme et lui parle par son entrée et sa sortie standard, comme deux
programmes reliés par un tuyau. Pas de réseau, pas de port, pas de certificat.

**Pourquoi stdio et pas HTTP.** Parce que le client lance lui-même le serveur,
donc il sait avec quels réglages il l'a lancé. C'est exactement ce dont nous
avons besoin pour fixer le profil, comme le chapitre 8 l'expliquera.

**Enveloppe.** La forme commune de toutes les réponses. Ici :
`{"status": ..., "payload": ..., "message": ...}`. Un client regarde toujours
`status` d'abord, et n'exploite `payload` que si tout va bien.

## 2.4 Autour de la gouvernance

**Profil.** Une identité de client, à laquelle des droits sont attachés.

**RBAC, contrôle d'accès par rôle.** L'idée qu'on n'attache pas des droits à des
personnes mais à des rôles, et des personnes à des rôles.

**Deny-by-default, refus par défaut.** Tout ce qui n'est pas explicitement
autorisé est refusé. C'est l'inverse d'une liste noire, où tout est permis sauf
ce qu'on a pensé à interdire. Le chapitre 7 raconte comment j'ai écrit une liste
noire en croyant faire du refus par défaut, et comment le contrôle ne l'a pas vu.

**Journal.** Un fichier où chaque appel laisse une ligne. Pas seulement les
appels réussis : **surtout** les refus, car c'est eux qu'un audit vient chercher.

---

# 3. La méthode de travail

Ce chapitre est court et vous fera gagner plus de temps que tous les autres.
Ce sont quatre règles, et elles viennent d'erreurs payées.

## 3.1 Mesurer plutôt qu'affirmer

Chaque fois que vous êtes tenté d'écrire « le modèle devrait », « ce sera plus
rapide », « ça ne peut pas arriver », arrêtez-vous et mesurez.

Sur ce projet, la mesure a **contredit mon intuition** au moins six fois :

- j'ai cru que le reclassement n'apportait presque plus rien. Vrai du
  classement, **faux de l'abstention**, où il change tout ;
- j'ai désigné une étape comme la plus fragile d'un fichier de construction.
  Elle n'a jamais échoué ; quatre autres ont cassé ;
- j'ai cru qu'un petit modèle de code saurait classer une question en deux
  catégories. Quatre montages mesurés, tous au niveau du hasard ;
- j'ai cru qu'un dimensionnement mémoire mesuré sur un service valait pour un
  autre. Il a saturé à 100 %.

**Corollaire pratique :** ne croyez jamais un message de confirmation qui
s'affiche indépendamment du résultat. J'ai deux fois écrit un script qui
affichait « terminé » alors que l'opération avait échoué, parce que le message
était après un tube qui masquait le code de retour.

## 3.2 Générer plutôt que recopier

C'est la règle qui structure tout le dépôt, et elle vient de **quatre**
occurrences du même incident.

Chaque fois qu'un fait existe à deux endroits, les deux **divergent**, et
personne ne s'en aperçoit. Sur ce projet :

- les énumérations de la base recopiées dans un document avaient perdu leurs
  accents. Une requête sur « Cablage » au lieu de « Câblage » rend **zéro
  ligne, sans erreur**, en franchissant toutes les barrières de sécurité ;
- le guide d'accès annonçait trois profils dont un qui n'existait pas, et
  donnait un outil comme interdit alors qu'il était autorisé ;
- le fichier de cas de test attendait des droits qui avaient changé ;
- les étiquettes de référence d'une mesure avaient été fabriquées
  mécaniquement, donc mesuraient contre une vérité en partie fausse.

**La règle :** un fait n'existe qu'à **un** endroit. Partout ailleurs, il est
**généré** depuis cet endroit, par un script. Et ce script sait dire « la copie
a divergé », de sorte qu'on l'apprend par un échec et non par un client mécontent.

## 3.3 Éprouver chaque contrôle en le faisant échouer

Un contrôle qu'on n'a jamais vu tomber ne prouve rien. Il peut être vide, mal
branché, ou tester autre chose que ce que son nom annonce.

**À faire, systématiquement :** après avoir écrit un contrôle, cassez
volontairement ce qu'il surveille et vérifiez qu'il échoue, **avec un message
qui nomme le fautif**. Puis remettez en état.

Sur ce projet, cette discipline a rattrapé un contrôle qui vérifiait une liste
contre une autre liste **du même fichier**. Retirer une colonne des deux
laissait dix-neuf contrôles sur dix-neuf au vert.

## 3.4 Dire ce qui ne marche pas

Un chiffre qui minimise une faiblesse est ce qui se paie le plus cher devant un
jury. Une limite énoncée avec sa cause est une preuve de maîtrise ; la même
limite découverte par l'examinateur est une faute.

Ce projet publie donc :

- que son générateur SQL réussit **17 questions sur 24**, avec la cause ;
- qu'un cas de test **échoue** et que l'attendu n'a pas été aligné dessus ;
- que sa mesure de gain porte sur trop peu de questions pour être
  statistiquement solide, avec le calcul qui le montre.

**Piège de conception que cela évite.** Si vous alignez un test sur le
comportement observé, vous transformez une limite en comportement attendu, et
elle disparaît du rapport. Un test doit dire ce qui **devrait** se passer.

---

# 4. Préparer son poste

## 4.1 Ce dont vous avez besoin

| Outil | Rôle | Version |
| --- | --- | --- |
| Python | le langage | **3.11**, ni plus ni moins |
| `uv` | gestion des dépendances et de l'environnement | récente |
| `git` | versionner | récente |
| un éditeur | écrire | au choix |

**Pourquoi Python 3.11 exactement.** Le fichier de verrouillage des dépendances
épingle cette plage. Avec 3.12, certaines bibliothèques n'ont pas de version
compatible et l'installation échoue de façon obscure.

**À faire :**

```
uv sync --extra vector --extra demo
```

Cette commande lit `pyproject.toml`, crée un environnement isolé et installe
tout. Les deux options ajoutent le nécessaire pour les modèles et pour
l'interface.

## 4.2 Deux pièges Windows, et ils ont coûté une demi-journée

**Piège 1 : Smart App Control.** Cette protection de Windows 11 bloque les
programmes non signés par un éditeur reconnu. Elle a bloqué le Python que `uv`
télécharge, avec l'erreur `0xC0E90002` **sans aucun message**, et un code de
sortie 127 depuis un terminal.

La solution n'est pas de désactiver la protection : c'est **irréversible sans
réinstaller Windows**. La solution est d'installer un Python **signé** :

```
winget install Python.Python.3.11
```

Cette protection a frappé une seconde fois, bien plus tard, en bloquant une
bibliothèque nécessaire à la production du document Word. Retenez le message :
« une stratégie de contrôle d'application a bloqué ce fichier ».

**Piège 2 : la virtualisation.** Si vous voulez Docker, il faut que VT-x soit
activé dans le firmware. Sur mon poste il était **désactivé**, ce qui se vérifie
ainsi :

```
powershell -c "(Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled"
```

Si cela répond `False`, Docker Desktop **affichera son interface sans que son
moteur démarre**, et toutes ses commandes rendront une erreur 500. Ne confondez
pas l'interface et le moteur. Cela se réactive au redémarrage dans le BIOS, et
peut être verrouillé par un service informatique.

**Bonne nouvelle :** vous n'avez pas besoin de Docker. Le chapitre 14 montre
comment construire une image **côté serveur**, sans aucun moteur local.

## 4.3 Le shell, et ses trois manières de vous trahir

Vous allez alterner entre PowerShell et un shell POSIX. Les trois pièges
suivants m'ont fait perdre du temps à plusieurs reprises :

**La continuation de ligne diffère.** En POSIX c'est l'antislash `\`, en
PowerShell c'est l'accent grave. Une commande copiée d'une documentation POSIX
échoue dans PowerShell avec « expression manquante après l'opérateur unaire ».
**Écrivez vos commandes sur une seule ligne** et le problème disparaît.

**Git Bash convertit les chemins.** Tout argument qui ressemble à un chemin
POSIX est réécrit en chemin Windows. En passant `SORABEL_DATA_DIR=/app/data` à
une commande, le programme distant a reçu
`C:/Program Files/Git/app/data`. Le service démarrait, servait ses pages, et
échouait à la première question avec une erreur qui ne disait rien de la cause.
Parade : `MSYS_NO_PATHCONV=1` devant la commande, ou n'employez pas de chemin
absolu là où un chemin relatif suffit.

**Les documents-ci-joints mangent les caractères.** Écrire du code Python dans
un shell par un « document en ligne » fait interpréter les antislashs et les
accents graves. J'ai ainsi cassé trois fichiers : un `\n` devenu un vrai saut de
ligne, un `\\` devenu une continuation, des accents graves remplacés par le
résultat d'une commande vide. **Écrivez le code dans un fichier**, puis
exécutez-le.

---

# 5. Les données

## 5.1 Ce qu'on reçoit

Deux choses, à ne pas versionner dans git car elles sont volumineuses :

**Une base SQLite**, avec cinq tables métier :

| Table | Lignes | Ce qu'elle contient |
| --- | --- | --- |
| `clients` | 60 | nom, segment, ville, courriel |
| `produits` | 120 | référence, libellé, prix, **prix d'achat**, **marge** |
| `stocks` | 312 | quantité par entrepôt, seuil de réapprovisionnement |
| `commandes` | 340 | date, statut, montant |
| `ventes` | 993 | ligne à ligne, avec **marge réalisée** |

**Un corpus de quatre cents fichiers** : fiches techniques et notices en PDF,
procédures du service client en HTML, notes internes en Markdown, avec des
numéros de version.

## 5.2 Relever le jeu de données, sans se tromper

**À faire, avant d'écrire une ligne de code métier :** écrivez un script qui
relève les faits du jeu de données et qui les écrit **dans** votre
documentation, entre deux balises. Donnez-lui un mode qui vérifie que le relevé
est à jour.

**Pourquoi c'est la première chose à faire.** Vous allez avoir besoin de connaître
les valeurs réelles : les statuts possibles d'une commande, les noms d'entrepôts,
la plage de dates. Si vous les recopiez à la main, elles dérivent, et une
requête sur une valeur mal orthographiée rend **zéro ligne sans erreur**. C'est
exactement ce qui m'est arrivé avec six valeurs dont les accents avaient été
perdus.

## 5.3 Trois pièges dans les données elles-mêmes

Regardez vos données avant de leur faire confiance. Les trois suivants ont
chacun changé une décision :

**Les libellés de produits sont dupliqués.** Quarante-trois libellés
apparaissent plusieurs fois avec des références différentes. Une question comme
« le prix du disjoncteur 40 A » n'a donc **pas une seule réponse** : il y en a
quatre. Cela impose de prévoir une réponse multiligne plutôt qu'un choix
arbitraire.

**La numérotation des commandes a des trous.** Un identifiant bien formé peut
ne correspondre à aucune ligne. Il faut distinguer « aucun résultat » de
« question mal comprise », sinon un utilisateur croira que sa commande a
disparu.

**Le corpus est massivement répétitif, et c'est le piège le plus grave.**
Mesurez ceci : retirez les titres, et comptez les corps de texte distincts.

| | Fichiers | Corps de texte distincts sans le titre |
| --- | --- | --- |
| Notices | 80 | **4** |
| Procédures du service client | 90 | **4** |

Autrement dit, **le titre est le seul signal qui distingue 170 des 400
fichiers**. Le chapitre 6 explique la règle d'une ligne qui en découle, et ce
qui se passe si on l'oublie.

## 5.4 Constituer les jeux d'évaluation

**À faire :** écrivez deux fichiers de questions, une par ligne, au format JSON.

| Fichier | Questions | Catégories |
| --- | --- | --- |
| questions documentaires | 30 | référence exacte, question couverte, hors corpus |
| questions base de données | 24 | métier, sécurité, ambiguïté, hors schéma |

Puis un troisième fichier, celui des **attendus** : pour chaque question, ce
qu'une bonne réponse contient. C'est votre **oracle**, le juge qui dit si une
réponse est correcte.

**Piège, et j'y suis tombé.** Ne fabriquez pas les attendus **mécaniquement**.
J'ai étiqueté des questions selon le fichier d'où elles venaient : celles du jeu
SQL en « base », celles du jeu documentaire en « document ». Or « quel est le
stock total de la REF-8842 ? » venait du jeu SQL, mais l'outil de stock y répond
aussi bien. **Cinq de mes vingt étiquettes étaient contestables**, et je
mesurais donc contre une vérité en partie fausse.

Prenez l'attendu là où il est légitime, et quand un cas est ambigu, dites-le au
lieu de trancher arbitrairement.

## 5.5 Les questions qui comptent plus que les autres

Sur trente questions documentaires, huit seulement portent réellement le socle
de la mesure : les autres sont hors corpus ou trop proches les unes des autres.
Sachez-le, et dites-le dans votre rapport. Prétendre mesurer sur trente
questions quand huit portent le résultat est une exagération qui se voit.

Repérez aussi les questions qui **démontrent une exigence**. « Quelle est la
marge sur la REF-8842 ? » n'est pas une question ordinaire : c'est celle qui
prouve E5. Si elle est mal traitée, une exigence devient invisible. Ces
questions méritent un contrôle à part, distinct de la moyenne générale.
# 6. Brique 1 : la recherche documentaire

C'est la brique la plus longue à construire, et celle où une seule ligne oubliée
ruine tout. Prenez-la dans l'ordre.

## 6.1 Le chemin complet

```
  fichiers  ->  Document  ->  Chunk  ->  vecteurs  ->  index
                                                          |
  question  ->  filtre du profil  ->  dense + BM25  ->  fusion RRF
                                          |
                                    reclassement  ->  seuil  ->  reponse + sources
```

Lisez-le deux fois. Chaque flèche est une décision, et nous les prenons une par
une.

## 6.2 Du fichier au Document

**À faire :** définissez une forme unique, appelons-la `Document`, vers laquelle
tous les formats convergent :

| Champ | Exemple |
| --- | --- |
| identifiant | `REF-8842-v2.1` |
| titre | `Fiche technique disjoncteur tetrapolaire 40 A` |
| référence | `REF-8842` |
| type | `fiche_technique`, `notice`, `procedure_sav`, `note_interne` |
| version | `2.1` |
| date | `2026-03-12` |
| texte | le contenu |

**Pourquoi une forme unique.** Sans elle, chaque format contamine tout le reste
de la chaîne, et vous écrivez trois fois la même logique. Un chargeur par
format, une forme commune, et tout ce qui suit ignore le format d'origine.

**Piège des métadonnées HTML.** Les procédures du service client portent leur
version dans une balise. J'avais noté dans mes documents de conception une forme
qui n'était pas la bonne, et un chargeur écrit d'après cette note aurait
silencieusement rendu une version vide. **Ouvrez un fichier réel** et regardez,
plutôt que de vous fier à une note.

**Piège des PDF, et il est sévère.** N'écrivez **jamais** d'expression
régulière sur un flux PDF. J'avais un motif maison pour extraire les titres :
il en perdait **47 sur 150**, en s'arrêtant sur une parenthèse échappée. Et il
ne signalait rien. Utilisez une bibliothèque de lecture de PDF, et posez à la
fin du chargement quelques assertions : le nombre de fichiers attendu, le
nombre de titres non vides, l'absence de doublon d'identifiant.

## 6.3 Le découpage en morceaux, et LA règle du projet

**À faire :** découpez chaque document en morceaux de quelques centaines de
mots, avec un léger recouvrement pour ne pas couper une phrase utile en deux.

Puis, et c'est **la règle la plus importante de tout le projet** :

> **Chaque morceau est préfixé de son titre, sa référence et sa version.**

Autrement dit, un morceau ne commence pas par « Étape 3 : dévisser le
capot » mais par « Fiche technique disjoncteur 40 A | REF-8842 | v2.1, puis Étape
3 : dévisser le capot ».

**Pourquoi, et voici la mesure.** Souvenez-vous du chapitre 5 : les 80 notices
ne portent que **4 corps de texte distincts** une fois les titres retirés. Sans
ce report :

| | Avec le report du titre | Sans |
| --- | --- | --- |
| Morceaux distincts, notices | 320 | **4** |
| Morceaux distincts, procédures | 360 | **4** |

Sans la règle, le moteur reçoit 320 morceaux quasiment identiques et en choisit
un **au hasard**. Il rend alors un titre, une référence, une version et une date
parfaitement formés : **E1 est formellement satisfaite, la citation est fausse,
et rien ne le signale**.

C'est le défaut le plus dangereux du projet, parce qu'il ne produit aucune
erreur. Vous ne le verrez que si vous vérifiez qu'une question sur la REF-8842
cite bien la REF-8842, et pas une autre.

## 6.4 Les versions

Un même document existe en plusieurs versions. Trois attitudes possibles, et
une seule est bonne.

| Attitude | Conséquence |
| --- | --- |
| N'indexer que la dernière | on perd l'historique, et une question sur l'ancienne version devient sans réponse |
| Indexer tout, sans distinguer | le moteur cite parfois la v1.0 quand la v2.1 existe. Inacceptable pour du matériel électrique |
| **Indexer tout, marquer la plus récente, citer celle-là** | correct |

**À faire :** groupez les documents par référence, marquez d'un drapeau
`is_latest` celui dont la version est la plus haute, et arbitrez à la fin de la
recherche : si deux morceaux du même groupe remontent, gardez le plus récent.
Une question qui demande explicitement une ancienne version peut la demander.

**Piège de l'ordre.** Faites cet arbitrage **après** le reclassement et non
avant. Le modèle de reclassement ignore les dates : si vous le laissez trancher
en dernier, il peut remettre une v1.0 devant une v2.1.

## 6.5 Le stockage des vecteurs

**Ce qu'il faut absolument** : pouvoir **filtrer avant de chercher**.

C'est le critère décisif, et j'ai d'abord justifié mon choix par un mauvais
motif, la simplicité. Le vrai motif est celui-ci : le profil support n'a pas
accès aux notes internes. Deux façons de le faire :

| Façon | Problème |
| --- | --- |
| Chercher partout, puis retirer les résultats interdits **après** | si les cinq meilleurs sont des notes internes, il ne reste **rien**, et la réponse est vide alors qu'un bon document existait au sixième rang |
| **Filtrer avant**, pour ne chercher que dans l'autorisé | correct : la profondeur de candidats est remplie de documents permis |

C'est pour cela que le choix du stockage n'est pas un détail de confort : sans
filtrage préalable, **E2 et E4 ne tiennent pas ensemble**.

**À faire :** prenez une base de vecteurs **embarquée**, c'est-à-dire une
bibliothèque et un dossier de fichiers, pas un service à lancer. Vous
supprimez ainsi une unité à déployer, et cela fonctionne sur un poste où la
virtualisation est bloquée.

**Ce que cela coûte, et dites-le :** un index dans le processus ne se partage
pas entre plusieurs instances. Ici l'indexation est hors ligne et faite une
fois, donc plusieurs serveurs peuvent lire le même dossier en lecture seule.
Si l'indexation devenait continue, il faudrait revenir à un service.

**Piège de reproductibilité, et il est retors.** La recherche approchée de ces
bases est **non déterministe** quand les scores sont très proches. Sur un corpus
répétitif comme le nôtre, les quasi ex æquo sont la règle. J'ai obtenu des
voisins **différents d'une exécution à l'autre**, alors que le vecteur de la
question était identique au bit près, vérifié par empreinte. Mes deux premières
mesures se contredisaient sans que je sache laquelle croire.

Parade en deux points : augmentez le paramètre d'effort de recherche de l'index,
et ajoutez un **départage déterministe**, par exemple par identifiant à score
égal arrondi. Puis vérifiez : quatre exécutions dans quatre processus doivent
rendre la même liste.

## 6.6 BM25, à côté

**À faire :** construisez l'index lexical **séparément**, et **partitionné par
type de document**. Ainsi le filtrage par profil s'applique aussi à la branche
lexicale, sans quoi vous auriez bouché une fuite et laissé l'autre ouverte.

## 6.7 La fusion

**À faire :** fusionnez les deux classements par RRF, sur les **rangs**.

**Piège :** ne fusionnez jamais sur les scores. Un cosinus de 0,87 et un score
BM25 de 14,2 ne sont pas comparables, et toute pondération que vous inventerez
sera arbitraire. Les rangs, eux, sont sur la même échelle par construction.

## 6.8 Le court-circuit des références

**À faire :** si la question contient une référence de la forme `REF-8842`,
allez la chercher **directement par filtre de métadonnée**, sans calculer aucun
vecteur, et mettez le résultat en tête.

**Pourquoi.** C'est exact, instantané, et cela répond à la moitié de E2 sans
dépendre d'un modèle. Le cas canonique du brief, « REF-8842 renvoie la fiche en
tête », devient une garantie et non une espérance.

## 6.9 Le reclassement, et la surprise

**À faire :** prenez les vingt à trente meilleurs candidats après fusion, faites
les noter par un modèle de reclassement, et reclassez.

**Ce que j'avais mal évalué.** J'ai écrit que le reclassement n'avait presque
plus de marge de progression. C'était vrai du **classement**, où la recherche
hybride plafonnait déjà. C'était **faux de l'abstention** :

| | Marge de séparation entre une bonne et une mauvaise réponse |
| --- | --- |
| Recherche dense | **0,0015** |
| Avec reclassement | **1,41** |

Mille fois plus large. Décider « je réponds » ou « je m'abstiens » sur un écart
de 0,0015 est illusoire ; sur 1,41 c'est un choix net. **Le reclassement
n'apporte presque rien au classement et presque tout à l'abstention.**

**Conséquence directe :** il vous faut **deux seuils d'abstention**, un par
échelle de score. Un cosinus vit entre 0 et 1 ; les notes d'un modèle de
reclassement sont des logits non bornés, souvent entre −10 et +10. Un seuil
unique pour les deux ne veut rien dire.

## 6.10 Composer la réponse

**À faire :** ne demandez pas à un modèle de rédiger la réponse. Prenez le ou
les meilleurs passages et rendez-les, accompagnés des sources.

**Pourquoi.** Faire rédiger un modèle par-dessus des passages justes ouvre une
occasion d'inventer là où il n'y en avait aucune. C'est E1 qui l'interdit en
esprit : la valeur ajoutée est de trouver le bon passage, pas de le paraphraser.

## 6.11 Un cas vécu, et il éclaire tout le chapitre

Pendant une démonstration, une question faisait s'abstenir les deux profils.
J'ai cru à une régression du reclassement : la recherche dense trouvait bien un
document, la chaîne complète le rejetait.

Vérification faite, **l'abstention était juste et c'est la branche dense qui
avait tort**. Le document s'intitulait « Point politique tarifaire », et la
question portait sur les remises. Le corps du document traite d'une revue de
prix sur l'outillage à main et **ne parle pas de remises**. Le modèle de sens
avait rapproché la question du **titre** ; le modèle de reclassement, qui lit
question et passage **ensemble**, a conclu que le passage ne répondait pas.

C'est exactement son travail. Et cela rend tangible ce que la mesure de gain
avait chiffré sans le rendre parlant.

---

# 7. Brique 2 : interroger la base en lecture seule

## 7.1 Le principe : la défense en profondeur

Une seule barrière se contourne. Empilez-en plusieurs, **indépendantes**, de
sorte que la chute de l'une ne suffise pas.

| Couche | Ce qu'elle fait |
| --- | --- |
| **0** | ne montrer au modèle que le schéma autorisé pour ce profil |
| **0 bis** | refuser explicitement sur un vocabulaire déclaré |
| **1** | ouvrir la base en lecture seule |
| **2** | analyser la requête et n'accepter qu'un `SELECT` |
| **3** | vérifier que toutes les tables et colonnes touchées sont permises |
| **4** | limiter le nombre de lignes et le temps d'exécution |
| **5** | renvoyer la requête avec le résultat |
| **6** | journaliser |

## 7.2 Couche 0 : le schéma borné au profil

**À faire :** introspectez la base pour obtenir son schéma réel, puis retirez
les tables et colonnes que le profil n'a pas le droit de voir. Le texte de
schéma envoyé au modèle est celui-là, et pas un autre.

| Profil | Tables visibles | Colonnes visibles |
| --- | --- | --- |
| `support` | 4 | 21 |
| `commercial` | 5 | 31 |

**Pourquoi c'est puissant.** Le support **ne voit pas exister** les colonnes de
marge. Il ne les filtre pas après coup, il ne sait pas qu'elles existent. C'est
la forme la plus solide du refus.

**Et voici sa conséquence inattendue.** Puisque le modèle ne peut pas nommer
`marge_pct`, que fait-il quand on lui demande « les cinq produits les plus
rentables » ? Il **substitue** une colonne visible et rend
`ORDER BY prix_vente_ht`. Aucune donnée sensible ne sort, mais **la réponse ne
répond pas à la question**, et rien ne le dit.

J'ai mesuré le même phénomène sur une table : la table des ventes est retirée
au support, et à « combien de lignes dans la table ventes ? » le modèle rend
`SELECT COUNT(*) FROM commandes`. Substitution silencieuse.

Retenez-le : **aucune couche ne vérifie le sens**. C'est une limite réelle, à
énoncer, et c'est le premier motif de la couche suivante.

## 7.3 Couche 0 bis : le refus explicite

**À faire :** déclarez, à côté de la table de droits, un petit vocabulaire par
colonne sensible : pour la marge, les mots « marge », « marges », « taux de
marge » ; pour le prix d'achat, « prix d'achat », « coût d'achat ». Si la
question contient l'un de ces termes et que la colonne est interdite au profil,
**refusez immédiatement**, avant tout appel au modèle.

**Trois motifs, et le troisième est le plus fort :**

1. le refus est **immédiat**, en moins d'une milliseconde ;
2. il est **imputable** : on sait quelle colonne l'a déclenché ;
3. sans lui, la question sensible reçoit une **réponse plausible et fausse**,
   par substitution, au lieu d'un refus.

**Avertissement à écrire dans votre code.** Cette couche n'a **aucune valeur de
sécurité propre**. Un utilisateur qui évite les mots du vocabulaire la
contourne. Ce qui protège, c'est la couche 3. La couche 0 bis sert la clarté et
l'imputabilité, pas la sécurité. Si vous la présentez comme une protection, vous
vous trompez et vous trompez votre lecteur.

**Piège de démonstration.** Cette couche court-circuite en zéro seconde, donc
elle **empêche de voir les couches suivantes travailler**. Prévoyez, pour votre
démonstration, une question équivalente qui n'emploie aucun mot du vocabulaire.
J'ai perdu du temps à croire qu'une couche ne fonctionnait pas, alors qu'elle
n'était jamais atteinte.

## 7.4 Couche 1 : la connexion en lecture seule

**À faire :** ouvrez la base en mode lecture seule, et ajoutez les réglages qui
interdisent l'écriture.

**Piège majeur, et j'ai reproduit le défaut pour en être sûr.** Cette couche
**ne bloque pas toute écriture**. Sur une connexion en lecture seule, il reste
possible de désactiver le réglage de lecture seule, puis d'attacher un **autre
fichier** de base et d'y écrire. J'ai ainsi **exfiltré 120 lignes de prix
d'achat** vers un fichier tiers, sans que la base métier soit touchée.

Ce qui protège réellement, c'est la couche 2, qui refuse `ATTACH` et les
réglages par **type d'instruction**. Deux couches sur le papier, **une** qui
tient. Écrivez-le noir sur blanc dans votre documentation : une protection
surestimée est plus dangereuse qu'une protection absente, parce qu'on cesse de
la surveiller.

## 7.5 Couche 2 : l'analyse syntaxique

**À faire :** analysez la requête avec une bibliothèque d'analyse SQL, et
n'acceptez que :

- **une seule** instruction, pour bloquer l'enchaînement par point-virgule ;
- dont la racine est un `SELECT` ;
- sans aucun nœud d'écriture ou d'administration : `INSERT`, `UPDATE`, `DELETE`,
  `CREATE`, `DROP`, `ATTACH`, `PRAGMA` ;
- sans **étoile de projection**, pour ne jamais rendre une colonne par accident.

**Piège, et il m'a coûté un test d'acceptation.** Mon contrôle de l'étoile
attrapait aussi celle de `COUNT(*)`, donc `SELECT COUNT(*) FROM commandes` était
**refusé**. C'était précisément la requête du test « combien de commandes en
avril ? ». Ne refusez que les étoiles **de projection**.

**Second piège de la même famille.** Mon contrôle refusait un `ORDER BY` portant
sur un **alias de résultat**, donc il refusait les requêtes de référence de mon
propre oracle. Il faisait passer pour des erreurs de modèle une erreur de
barrière. Vérifiez qu'aliaser une colonne interdite reste refusé, mais laissez
passer un alias légitime.

## 7.6 Couche 3 : le périmètre, et sa portée exacte

C'est la couche qui protège vraiment. Elle mérite une lecture attentive.

**À faire :** parcourez l'arbre de la requête, relevez **toutes** les tables et
**toutes** les colonnes mentionnées, et vérifiez que chacune est permise au
profil.

**Le mot important est « toutes ».** J'avais d'abord décrit le périmètre sur
« les colonnes touchées », une notion tournée vers la **sortie**. C'était un
trou, et voici pourquoi.

```
SELECT reference FROM produits ORDER BY marge_pct DESC LIMIT 5
```

La colonne interdite n'est **pas affichée**. Elle sert au tri. Le résultat
divulgue pourtant le classement par marge, ce qui est l'essentiel de
l'information.

Pire, avec un prédicat :

```
SELECT reference FROM produits WHERE marge_pct > 40
```

En faisant varier le seuil, on retrouve la valeur exacte par dichotomie. J'ai
reconstitué de cette façon la marge d'un produit réel sur la base réelle.

**Donc :** le périmètre porte sur **toute occurrence** d'une colonne : dans les
colonnes affichées, dans un `WHERE`, dans une jointure, dans un `GROUP BY`, un
`HAVING`, un `ORDER BY`, dans une fonction d'agrégat et dans les sous-requêtes.

## 7.7 Couche 4 : la limite

**À faire :** imposez un nombre maximal de lignes, par exemple 200, et un délai
d'exécution maximal.

**Exception à prévoir :** un agrégat scalaire, comme un `COUNT`, rend une seule
ligne ; y ajouter une limite n'a pas de sens et brouille la lecture de la
requête renvoyée.

## 7.8 Couche 5 : renvoyer la requête

**À faire :** la requête générée part **toujours** avec le résultat.

**Précision de portée, elle m'a été utile.** E3 dit que la requête est
« renvoyée avec le résultat ». L'obligation porte sur l'**outil**, qui doit la
mettre dans sa réponse. **L'afficher** dans une interface est un choix de
présentation. Un écran destiné à un intégrateur la montre en permanence ; une
conversation destinée à un agent du service client peut la replier, car cet
agent ne lit pas de SQL.

**Une chose ne se replie jamais :** la requête d'un appel **refusé**. Un refus
sans sa requête n'est pas auditable, et c'est exactement là que voir le SQL
compte le plus.

## 7.9 Le prompt, et le mensonge qu'il enseigne

**À faire :** construisez le message envoyé au modèle avec, dans l'ordre :

1. le schéma **borné au profil**, avec un commentaire par colonne ;
2. les **valeurs réelles** des colonnes énumérées, relevées dans la base ;
3. les **chemins de jointure** canoniques, avec leur condition exacte ;
4. quelques exemples de questions et de réponses attendues ;
5. une **sortie typée** : le modèle doit répondre soit une requête, soit une
   demande de précision, soit « hors schéma ».

**Pourquoi la sortie typée.** C'est ce qui permet de répondre « je ne sais pas »
sans inventer. Sans elle, un modèle produit toujours *quelque chose*.

**Piège, et c'est le plus subtil du projet.** Mes exemples contenaient cette
ligne :

```
HORS_SCHEMA: le schema ne contient aucune donnee meteorologique
```

Bien plus tard, en production, le bot du profil commercial a répondu à « quelle
est la marge sur la REF-8842 ? » :

```
le schema ne contient aucune donnee de marge
```

**C'est faux.** Le profil commercial n'a aucune colonne interdite, et la marge
figure bien à son schéma. Le modèle avait recopié la tournure de **mon exemple**
en substituant un mot, et ce texte libre remontait tel quel à l'utilisateur.

Une justification inventée est **pire qu'un refus sec** : elle fait croire à une
règle qui n'existe pas, et un intégrateur qui la lit conclut à tort que la
donnée est hors de son périmètre.

**La correction :** ne propagez **jamais** le texte libre du modèle comme
justification. Rendez un message déterministe qui n'affirme que ce que vous
savez : « aucune requête n'a pu être produite pour cette question ; cela ne
signifie pas que la donnée est hors de votre périmètre ». Gardez le texte du
modèle dans votre trace technique, pour le diagnostic.

C'est l'esprit de E1, « ne jamais inventer », appliqué au chemin SQL. On y pense
pour les réponses documentaires et on l'oublie pour les refus.

## 7.10 Le choix du modèle, et sa limite mesurée

**À faire :** commencez par un petit modèle de code en local, mesurez, et ne
montez en gamme que si la mesure l'exige.

Voici ma mesure, sur 24 questions :

| Catégorie | Résultat |
| --- | --- |
| Sécurité (écritures, colonnes interdites) | **8/8** |
| Métier | 8/12 |
| Ambiguïté | 0/2 |
| **Total** | **17/24** |

**Ce que ce tableau dit vraiment.** Les barrières sont parfaites, huit sur huit.
Ce qui manque est la **capacité de traduction**. Autrement dit, la gouvernance
tient et la qualité de génération est le facteur limitant.

**Et la limite est matérielle, pas logicielle.** Sur mon poste, le processeur
tombe à 801 MHz sur 2304 sous charge. Un modèle de 7 milliards de paramètres y
produit 0,38 jeton par seconde, contre 3 à 8 attendus, et le même appel a pris
30 secondes puis 208 selon l'échauffement. J'ai monté l'échelle jusqu'en haut :
elle sature sur le matériel.

**À écrire dans votre dossier :** l'échelon suivant, si la qualité doit monter,
est un service d'inférence hébergé **dans le locataire du client**, pas un
service tiers. La différence est que les questions ne quittent pas
l'organisation.

## 7.11 Deux outils figés, et pourquoi ils existent

En plus de l'outil générique, prévoyez deux outils dont la requête est
**écrite à la main** : l'état du stock d'une référence, et le statut d'une
commande.

**Pourquoi.** Ce sont les deux questions les plus fréquentes du service client.
Une requête figée est instantanée, déterministe, et ne dépend d'aucun modèle.
C'est la meilleure réponse possible à une question connue d'avance.

**Attention :** ces requêtes ne passent pas par les six couches, puisqu'elles ne
sont pas générées. Prévoyez donc un test dédié qui vérifie qu'elles ne rendent
aucune colonne sensible. Le contrôle que vous supprimez, remplacez-le.

## 7.12 Le trou que les barrières ne comblent pas

Soyez honnête sur ce point, il vous sera posé.

« Qui est le PDG de Sorabel ? » produit une requête SQL **valide** sur une table
**autorisée**. Toutes les couches passent. Aucune ne vérifie le **sens** de la
requête, ni que la question relevait de la base.

E3 dit « pas de SQL halluciné ». Cette partie de l'exigence dépend donc de la
qualité du modèle, et non des barrières. Écrivez-le : les couches garantissent
qu'aucune écriture ne passe et qu'aucune colonne interdite ne sort. Elles ne
garantissent pas la pertinence.

---

# 8. Brique 3 : la gouvernance

## 8.1 Une seule source de vérité

**À faire :** écrivez un **unique** fichier de configuration, en YAML, qui
contient :

- le catalogue fermé des huit outils ;
- les collections de documents, avec leur type et leur dossier d'origine ;
- la classification des colonnes ;
- pour chaque profil : ses outils, ses collections, ses tables, ses colonnes
  interdites ;
- le vocabulaire de refus de la couche 0 bis.

**Pourquoi un fichier et non du code.** Parce que ce fichier se relit sans
savoir programmer, et qu'un responsable de la sécurité doit pouvoir le lire.

**Piège que j'ai créé moi-même.** Ce fichier était cité par ma documentation
depuis des jours, **et il n'existait pas**. La table de droits vivait recopiée
en clair à **trois** endroits. Une divergence de droits, contrairement à une
divergence de vocabulaire, ne se voit pas : **elle s'exploite**.

Et la divergence était déjà là : un des trois exemplaires donnait toutes les
tables à un profil là où un autre en énumérait cinq.

**À faire :** les trois exemplaires deviennent des **vues générées**, avec une
règle de préséance écrite au-dessus : en cas de divergence, c'est le fichier qui
fait foi.

## 8.2 Les invariants, écrits hors du fichier qu'ils contrôlent

**À faire :** écrivez un script de vérification qui joue une trentaine de
contrôles sur ce fichier, et qui **génère** ensuite une version lisible.

**Le point crucial :** les valeurs attendues doivent être écrites **en dur dans
le script**, et non lues dans le fichier vérifié.

**Pourquoi, et c'est mon erreur la plus instructive.** J'avais écrit un contrôle
qui vérifiait la liste des colonnes sensibles **contre une autre liste du même
fichier**. Retirer une colonne des deux listes laissait **dix-neuf contrôles sur
dix-neuf au vert**. Le contrôle ne contrôlait rien : il comparait un fichier à
lui-même.

Un invariant doit être **ancré ailleurs** que dans ce qu'il surveille.

## 8.3 La classification exhaustive des colonnes

**À faire :** classez **chaque** colonne de la base dans exactement une
catégorie : sensible, restreinte, ou publique. La somme des trois doit être
égale au schéma, et une colonne non classée fait **échouer** le contrôle.

**Pourquoi l'exhaustivité change tout.** Avec une simple liste noire, une
colonne ajoutée à la base plus tard est **publique par omission**. Avec une
classification exhaustive, elle est **non classée**, donc le contrôle tombe, et
quelqu'un doit décider. C'est la différence entre un oubli silencieux et une
décision.

Cette règle m'a obligé à classer une colonne à laquelle je n'avais pas pensé :
le courriel des clients. Elle n'est pas nommée par l'exigence E5, qui ne parle
que de prix et de marges. Mais le schéma fourni par la direction informatique
l'annote « donnée personnelle : usage interne uniquement », et le profil support
est un bot tourné vers l'extérieur. Elle est donc **restreinte**, et le motif
n'est pas mon goût mais une pièce du dossier.

## 8.4 Appliquer la table à deux niveaux

**À faire :** vérifiez les droits **deux fois**, à deux endroits différents.

| Niveau | Ce qu'il vérifie |
| --- | --- |
| La porte d'entrée | ce profil a-t-il le droit d'appeler cet outil ? |
| Dans l'outil | ce profil a-t-il le droit de voir cette collection, cette table, cette colonne ? |

**Pourquoi deux fois.** Parce qu'un outil peut être légitime et une ressource
non. Le support a le droit d'interroger la base ; il n'a pas le droit de voir
les marges. Un seul niveau ne sait pas exprimer cela.

## 8.5 Le défaut de conception qu'il faut éviter à tout prix

Voici le plus grave, et je l'avais commis dans mon dossier initial.

Mon catalogue faisait du **profil un paramètre d'outil**. Le client appelait
donc `ask_database(profil="support", question="...")`.

**Ce paramètre est rempli par le client.** Le bot du service client n'avait
qu'à se déclarer `commercial` pour obtenir les marges. L'exigence E4 était
**décorative**.

**La règle à retenir :** le profil n'est **jamais** une donnée de la requête. Il
est une **propriété du serveur**, fixée à son lancement, immuable pour la vie du
processus.

Concrètement : le serveur lit son profil dans une variable d'environnement au
démarrage, le valide, et **refuse de démarrer** si elle est absente ou inconnue.
Aucun outil ne reçoit de profil en paramètre.

**Conséquence à assumer :** pour servir deux profils, il faut **deux
processus**. Ce n'est pas un contournement, c'est la topologie normale de ce
protocole, et c'est même ce qui rend la démonstration convaincante : deux
processus, la **même** image, la **même** table de droits, le **même** journal,
et deux décisions opposées qui se lisent à la suite.

## 8.6 Ce qu'un mécanisme d'identité peut et ne peut pas

Vous vous demanderez s'il faut un fournisseur d'identité. Voici la frontière, et
elle vaut d'être écrite dans votre dossier :

> **Un fournisseur d'identité dit *qui*. La table de droits dit *quoi*.**

Certains fournisseurs savent aussi faire de l'autorisation applicative. **Ne
vous en servez pas** : vous encoderiez la table de droits une seconde fois, et
votre fichier cesserait d'être la source unique. Le fichier ne bouge pas, quel
que soit le mécanisme d'identité.

Ce qu'un fournisseur d'identité apporte réellement, par rapport à une variable
d'environnement : l'**expiration** et la **révocation**. Pas la conformité.

## 8.7 Le journal

**À faire :** écrivez un fichier au format « une ligne de JSON par appel », en
ajout seulement.

| Champ | Pourquoi |
| --- | --- |
| horodatage | pour ordonner |
| profil | pour savoir qui |
| outil | pour savoir quoi |
| arguments | pour savoir quelle question |
| statut | autorisé, refusé, erreur |
| message | pour comprendre un refus |
| durée | pour repérer les lenteurs |
| requête SQL | **même si l'appel est refusé** |

**Pourquoi ce format et pas une base.** Une ligne complète par appel résiste à
un arrêt brutal : on peut perdre la dernière ligne, jamais corrompre les
précédentes. Et cela se lit sans outil, ce qui compte le jour où vous l'ouvrez
devant quelqu'un.

**Ce qui n'y entre pas :** aucune valeur de résultat. Les **ressources
touchées** suffisent à un audit pour compter les accès tentés à une colonne
sensible, sans recopier la donnée. Un journal qui contient ce qu'il surveille
devient lui-même une fuite.

## 8.8 L'oracle de gouvernance

**À faire :** écrivez un fichier de cas, chacun décrivant un profil, un outil,
des arguments, et l'issue attendue. Une vingtaine suffit si chacun démontre une
chose distincte.

**Piège, et c'est la troisième occurrence du même incident.** J'avais écrit ce
fichier, puis la table de droits a changé, et **le fichier n'a jamais été
réaligné**. Il était périmé sur **cinq axes** en même temps : les droits, un
profil qui n'existait plus, deux statuts hors contrat, des noms d'arguments
périmés, et des clés de journal dans une autre langue.

**Un oracle faux est plus dangereux qu'un oracle absent :** il fait échouer un
serveur juste, ou pire, réussir un serveur faux.

**La parade :** un script qui confronte chaque cas à la table de droits, au
catalogue et au contrat. Et le contrôle décisif va dans **les deux sens** :

- une attente de refus sur un outil **accordé** est fausse ;
- une attente d'autre chose qu'un refus sur un outil **non accordé** est fausse
  aussi.

C'est le second sens qui manquait, et c'est lui qui aurait attrapé la dérive.

## 8.9 Comment consigner un échec sans le maquiller

Vous rencontrerez un cas où le comportement attendu est juste mais où le
système échoue, pour une raison connue et documentée. Deux mauvaises réponses et
une bonne :

| Réponse | Effet |
| --- | --- |
| Aligner l'attendu sur le comportement observé | la limite disparaît du rapport, transformée en comportement attendu |
| Retirer le cas | la limite disparaît aussi |
| **Garder l'attendu, et déclarer la limite à côté** | correct |

**À faire :** ajoutez au cas un champ qui déclare la limite, en exigeant qu'il
**nomme une décision du projet et une cause étayée**. Le cas reste en échec, et
l'échec reste visible.

**Et le garde-fou que cela demande.** Ce mécanisme pourrait servir à enterrer des
échecs un par un. Je l'ai éprouvé : un champ bien formé mais creux franchit tous
les contrôles textuels, parce qu'un script ne juge pas la sincérité d'une prose.

Mais il peut **compter**. D'où un **plafond** : au-delà de deux limites
tolérées, le contrôle échoue. L'accumulation se ferait un cas à la fois sans que
rien ne sonne ; relever le plafond doit rester un geste délibéré, visible en
relecture de code.
# 9. Le serveur : assembler les trois briques

## 9.1 Le contrat, à respecter à la lettre

Si votre projet est évalué par une suite de tests fournie, ce contrat n'est pas
négociable. Relevez-le **avant** de coder :

| Point | Valeur |
| --- | --- |
| Lancement | `python -m mcp_server.server`, communication par entrée et sortie standard |
| Profil | lu dans une variable d'environnement, ici `SORABEL_PROFILE` |
| Journal | chemin lu dans `GATEWAY_JOURNAL` |
| Réponse | `{"status", "payload", "message"}` |
| Statuts | `ok`, `refused`, `clarification`, `hors_corpus`, `error`. **Cinq, et pas un de plus** |
| Sources | champs `titre`, `reference`, `date` |

**Piège de vocabulaire, et il m'a coûté cher.** J'avais conçu neuf codes de
refus détaillés, du genre `UNAUTHORIZED_TOOL` ou `FORBIDDEN_COLUMN`. Ils ne sont
pas au contrat. Ils sont donc devenus **internes** : ils voyagent dans la charge
utile, jamais à la place du statut. Un client aiguille sur les cinq statuts, et
lit le code pour affiner.

Plus généralement : tout ce qui est **reformulé** dérive. Sur ce projet, le fond
de la conception a tenu ; ce sont les **noms** qui avaient bougé, et un droit
d'accès sur deux.

## 9.2 Le point de passage unique

C'est la décision d'architecture la plus importante du serveur.

**À faire :** écrivez **une** fonction par laquelle **tout** appel passe. Elle
fait, dans cet ordre :

1. vérifier que le profil a le droit d'appeler cet outil ;
2. sinon, refuser ;
3. sinon, appeler la logique métier ;
4. attraper toute exception et la transformer en statut `error` ;
5. **journaliser** ;
6. rendre l'enveloppe.

**Pourquoi.** Parce qu'il n'y a alors **pas de second chemin**, donc pas de
chemin qui aurait oublié de journaliser. E5 devient vraie **par construction**
et non par vigilance. C'est une propriété que vous pouvez affirmer sans crainte,
et démontrer en montrant la fonction.

**Corollaire :** journalisez **avant** de rendre la réponse, jamais après. Si le
code plante entre les deux, vous voulez que la trace existe.

## 9.3 Le catalogue borné au profil

**À faire :** quand un client demande la liste des outils, ne rendez que ceux
que son profil peut appeler.

**Pourquoi.** On n'annonce pas ce qu'on va refuser. C'est une politesse, et
c'est aussi une réduction de surface : un outil dont on ignore l'existence n'est
pas sondé.

**Mais gardez le refus quand même.** Un client peut appeler un nom qu'il n'a pas
vu. Ce nom doit être refusé avec le même code que n'importe quel outil interdit,
et non provoquer une erreur technique. C'est cela, le refus par défaut.

## 9.4 Aucun paramètre obligatoire, et c'est délibéré

**À faire :** dans la description des outils, **ne déclarez aucun paramètre
comme obligatoire**.

**Pourquoi, et c'est contre-intuitif.** Le contrôle du **droit** doit précéder la
validation du **schéma**. Sinon, un client sans droit sur un outil, qui
l'appellerait avec des arguments vides, recevrait une erreur de protocole au
lieu d'un refus de gouvernance.

Or c'est exactement ce que fait une suite de tests : elle appelle chaque outil
interdit avec un objet d'arguments vide, et attend un refus. Si votre schéma
refuse d'abord, votre gouvernance ne s'exprime jamais.

## 9.5 Serveur bas niveau plutôt que cadre tout fait

**À faire :** utilisez l'interface de bas niveau du protocole, et non le cadre
qui génère tout automatiquement.

**Pourquoi.** Parce que vous voulez garder la main sur l'ordre exact des
contrôles, et notamment désactiver la validation automatique des arguments pour
la raison qui précède. Un cadre qui décide à votre place vous prive de la
décision qui compte.

## 9.6 Le préchauffage, et le piège de concurrence

Les modèles prennent du temps à charger. Sur mon poste, le premier appel a coûté
**677 secondes**, contre 12 à 20 pour les suivants. Or une suite de tests
accorde souvent 30 secondes par appel, et démarre un **processus serveur neuf**.

**À faire :** au démarrage, chargez les modèles dans un fil d'arrière-plan, pour
que le serveur réponde tout de suite au protocole tout en préparant les modèles.

**Piège de concurrence, et il a fait tomber huit tests d'un coup.** Ma première
version faisait **les imports** dans le fil d'arrière-plan. Les imports de
bibliothèques scientifiques ne sont pas sûrs en concurrence : le fil de requête
et le fil de préchauffage importaient en même temps, et j'obtenais une erreur
d'import sur un module partiellement initialisé.

**La règle :** faites les **imports dans le fil principal**, et seulement le
**chargement des poids** dans le fil secondaire.

**Et dites ce que le préchauffage ne résout pas.** Sur du matériel lent, 677
secondes ne rentrent pas dans un budget de 30 secondes, quoi qu'on fasse. Le
préchauffage aide, il ne fait pas de miracle.

## 9.7 Le guide d'accès, et pourquoi il doit être généré

**À faire :** écrivez un court guide pour l'intégrateur : les outils par profil,
les ressources par profil, la forme des réponses, la signification des statuts.

**Piège, et c'est la deuxième occurrence.** Mon guide était **gravement
périmé** : trois profils dont un inexistant, un outil donné comme interdit
alors qu'il était autorisé, un autre l'inverse, un nom de variable faux, et des
noms de champs qui n'existaient nulle part dans le code.

**Un guide d'accès faux est pire qu'un guide absent : l'intégrateur lui fait
confiance.**

**La parade :** un script qui **génère** les tableaux du guide depuis les deux
seules sources qui font foi : le fichier de droits, et **le serveur lui-même**,
en appelant réellement les huit outils pour relever la forme des réponses. Plus
un contrôle des affirmations textuelles qui ne se génèrent pas, comme le nom
d'une variable.

**Effet de bord utile :** ce relevé vérifie au passage que les huit outils
fonctionnent de bout en bout.

---

# 10. Mesurer

## 10.1 Pourquoi la mesure est un livrable

E6 exige une preuve chiffrée. Mais au-delà de l'exigence, la mesure est ce qui
vous évite d'affirmer des choses fausses, et vous en affirmerez.

**À faire, dans cet ordre :** écrivez le **protocole** de mesure **avant**
l'implémentation. Vous ne pouvez pas choisir votre méthode après avoir vu les
résultats sans vous suspecter vous-même.

## 10.2 L'ablation : comparer quatre configurations, pas deux

**À faire :** comparez quatre configurations et non deux.

| Clé | Dense | BM25 et fusion | Reclassement | Court-circuit des références |
| --- | :---: | :---: | :---: | :---: |
| **A**, la base de comparaison | oui | non | non | non |
| **B** | oui | oui | non | non |
| **C** | oui | oui | oui | non |
| **D**, le système complet | oui | oui | oui | oui |

**Pourquoi quatre.** Comparer seulement A et D ferait varier trois choses à la
fois, et le gain global ne serait imputable à rien. Avec quatre configurations,
chaque écart s'attribue à un composant.

## 10.3 Séparer les populations de questions

**À faire :** mesurez séparément les questions **par référence exacte** et les
questions **couvertes en langage naturel**. Et comptez à part les questions
**hors corpus**, qui ne mesurent pas un rappel mais une abstention.

**Piège :** une moyenne sur les trois populations mélangées ne veut rien dire,
parce que le court-circuit des références fait un bond sur la première et rien
sur les deux autres.

## 10.4 Compter sur des documents, pas sur des morceaux

**À faire :** dédupliquez par document avant de compter.

**Pourquoi.** Une notice fait quatre morceaux. Si vous comptez les trois
meilleurs **morceaux**, ils peuvent tous appartenir au même document, et votre
chiffre ne veut plus rien dire. Ce qui intéresse l'utilisateur, c'est de
recevoir le bon **document**.

## 10.5 Publier les résultats avec leur incertitude

Voici mes résultats :

| Population | A dense | B hybride | C reclassé | D complet |
| --- | :---: | :---: | :---: | :---: |
| Référence exacte, premier résultat | 0,875 | 0,875 | **1,000** | 1,000 |
| Question couverte, premier résultat | 0,778 | 0,889 | **1,000** | 1,000 |

Et voici ce que le rapport dit **aussi**, dans le même souffle :

- le socle vaut **8 à 9 questions notables** ;
- sur huit questions, **une bascule vaut 12,5 points** ;
- les **intervalles de Wilson** à 95 % de 6/8 et de 4/8 se **recouvrent
  entièrement** ;
- le test approprié pour comparer deux systèmes sur les mêmes questions est
  celui de **McNemar**, et il donne **p = 0,5**.

**Pourquoi il faut l'écrire.** Un « +25 points » annoncé sans intervalle sur un
jeu de cette taille ne résiste pas à une question de jury. En l'écrivant
vous-même, vous montrez que vous savez ce que votre chiffre vaut. C'est plus
convaincant qu'un chiffre plus gros.

**À faire :** publiez aussi une **lecture** et pas seulement un tableau : sur
quelles questions le gain se concentre, lesquelles échouent dans les deux
branches, et ce que cela dit des limites.

## 10.6 Ne pas comparer ce qui n'est pas comparable

**Piège que j'ai identifié et évité de justesse.** J'ai voulu comparer
l'abstention entre la configuration de base et la configuration complète. C'est
impossible honnêtement : le seuil d'abstention porte sur les notes du modèle de
reclassement, et la configuration de base **n'a pas de reclassement**.

Forger pour elle un second seuil reviendrait à **choisir le résultat** : un
seuil bas la fait inventer sur toutes les questions hors corpus et donne 100
points de gain au système complet ; un seuil haut la fait s'abstenir partout et
lui coûte tout son rappel. Le chiffre publié serait une conséquence de mon
choix.

**Donc :** la ligne « abstention » ne porte que sur la branche complète, et se
lit comme une garantie de E1, **pas** comme un gain de E6. Dites-le dans votre
rapport.

## 10.7 Générer le rapport

**À faire :** le rapport de mesure est **généré** par un script, jamais écrit à
la main.

**Piège que cela évite, et que j'ai créé.** Mon document de protocole portait un
gabarit de tableau vide, « à remplir plus tard ». Le lot correspondant a été
fait, les chiffres existaient dans le rapport généré, et le gabarit est resté
vide pendant des jours. Pire, le remplir à la main aurait créé une **seconde
vérité**, qui dériverait au premier réindexage.

**La bonne résolution :** le document de protocole **renvoie** au rapport généré,
et si vous y recopiez deux chiffres pour l'ordre de grandeur, écrivez
explicitement qu'en cas de divergence c'est le rapport qui fait foi.

---

# 11. L'interface

## 11.1 Le piège de l'interface, et il est mortel

Une interface qui montre une réponse documentaire et un tableau de résultats
montre **un chatbot**. Elle ne démontre **ni E4 ni E5**, c'est-à-dire pas la
gouvernance, qui est le sujet du projet.

Or c'est le premier livrable que l'évaluateur ouvrira, avant votre dossier et
avant vos journaux.

**À faire :** décidez **ce que chaque écran prouve**, et écrivez l'exigence
**sur l'écran**.

| Exigence | Ce qui la rend visible | Écran |
| --- | --- | --- |
| E1 | les sources sous chaque réponse, et une abstention affichée en clair | 1 |
| E2 | une référence exacte et une question en langage naturel, les deux aboutissent | 1 |
| E3 | le SQL à côté du résultat, et une écriture refusée | 2 |
| **E4** | le **même appel**, deux profils, deux issues côte à côte | 3 |
| **E5** | idem sur une colonne sensible, plus le journal en direct | 3 et 4 |
| E6 | le tableau d'ablation avec ses intervalles | 5 |

**L'écran 3 est l'écran principal**, celui qui justifie l'existence de
l'interface. Deux colonnes, une seule question saisie une seule fois, envoyée
aux deux profils.

## 11.2 Comment montrer deux profils, alors qu'un serveur n'en a qu'un

Contradiction apparente : le profil est figé au lancement, mais il faut montrer
deux profils.

**La résolution :** **deux processus**, la même image, la même table de droits,
un journal **partagé**. Ce n'est pas un contournement : c'est ce qui rend la
comparaison vérifiable, puisque les deux décisions opposées se lisent **à la
suite dans le même fichier**.

## 11.3 Ce que l'interface n'est pas

**À écrire sur l'écran d'accueil**, car cela évite des questions et montre que
les choix sont assumés :

- **pas d'authentification** : l'interface n'identifie personne. Elle démontre
  une table de droits, pas une gestion d'identité ;
- **pas de sélecteur de profil** : le profil est une propriété du serveur ;
- **pas de refus « joli »** : un refus s'affiche avec son code et sa cause ;
- **aucune écriture possible**, sur aucun chemin.

## 11.4 Le client persistant, et pourquoi il est indispensable

Une interface web se réexécute à chaque interaction. Si vous ouvrez une session
serveur par clic, chaque bouton relance un processus et recharge les modèles :
plusieurs dizaines de secondes par clic.

**À faire :** gardez **une session ouverte par profil**, dans un fil qui porte
sa propre boucle d'événements, et soumettez-lui les appels depuis le fil
principal.

Mesure : session ouverte en **16 secondes**, puis appels à **0,01 seconde**.

**Ce n'est pas un contournement du protocole**, c'est ce que fait tout client
durable : un environnement de développement ne relance pas son serveur à chaque
complétion.

**Piège que cela introduit, et il m'a coûté deux diagnostics.** Une session
gardée peut **mourir** : si le processus serveur est tué, par exemple faute de
mémoire, la session reste en place et **tous** les appels suivants échouent,
définitivement. Le service paraît cassé alors qu'il suffirait de relancer.

**À faire :** distinguez une **session morte** d'un simple délai dépassé,
rouvrez **une fois**, et rejouez l'appel. Une seule fois, pour ne pas boucler si
le serveur meurt à chaque démarrage.

## 11.5 Le piège de l'assemblage

**Piège que seul l'assemblage révèle.** Le réglage de page d'une interface web
ne peut souvent être appelé qu'**une fois par exécution**. Mes trois pages
l'appelaient chacune : **chacune marchait seule, et l'ensemble tombait**.

**À faire :** un petit utilitaire qui règle la page **si personne ne l'a déjà
fait**, sans jamais échouer. Chaque page reste alors lançable seule, et
l'assemblage fonctionne.

**Leçon générale :** testez l'assemblage, pas seulement les pièces. Un défaut
qui n'apparaît qu'à l'assemblage est invisible tant qu'on teste isolément.

## 11.6 Vérifier qu'une interface fonctionne réellement

**Piège, et mon premier contrôle ne mesurait rien.** J'ai lancé le serveur web,
demandé la page, obtenu un code 200, et conclu que tout allait bien.

**Faux.** Beaucoup de cadres web n'exécutent le script qu'à la **connexion d'un
navigateur**. Un code 200 sur le port prouve que le serveur écoute, **pas** que
votre code s'exécute.

**À faire :** utilisez le harnais de test officiel de votre cadre, qui exécute
réellement le script et vous rend les exceptions. Puis **cliquez les boutons**
dans ce harnais. Un bouton non cliqué est un bouton non testé.

---

# 12. L'assistant conversationnel

## 12.1 Ce que cela change

Les écrans techniques laissent l'humain choisir son onglet, donc son outil. Une
**conversation** ne peut pas : l'utilisateur pose une phrase et ignore qu'il
existe huit outils.

Il faut donc **router** : décider quel outil appeler depuis du texte libre.

**Et voici le point qui m'a le plus servi :** c'est exactement le cerveau dont
un bot de messagerie a besoin. Le bot reçoit une phrase et doit faire ce même
choix. Ce ne sont donc pas deux chantiers mais **un seul**, avec deux devantures.

## 12.2 Le routage : ce qui échoue, mesuré

J'ai d'abord confié le routage au petit modèle local déjà présent, avec une
sortie contrainte. **Quatre montages mesurés, tous au niveau du hasard :**

| Montage | Juste |
| --- | --- |
| Comparaison des probabilités du premier mot de chaque étiquette | 4/20 |
| Choix multiple A/B/C/D | 6/20 |
| Choix multiple avec calibration | 5/20 |
| Génération libre puis lecture | 1/20 |
| Choix à deux classes | 28/54, en répondant **toujours** la même chose |

Pour quatre étiquettes, le hasard donne 5/20. Tous les montages y étaient.

**Deux causes, et l'une est de moi.** D'abord, c'est un modèle de **code** de
0,5 milliard de paramètres : la classification en français libre est hors de sa
portée. Ensuite, mon premier montage comparait les probabilités brutes du
premier mot de chaque étiquette. Or ces probabilités incorporent la **fréquence
a priori** de chaque mot dans le vocabulaire du modèle : je comparais des choses
non comparables, et la fréquence du mot écrasait la réponse.

## 12.3 Le routage : ce qui marche

**À faire :** combinez deux mécanismes.

**Un vocabulaire déclaré, relevé et non recopié.** Prenez les noms de tables et
de colonnes de la base par introspection, plus le vocabulaire de refus déjà
déclaré, plus une liste de verbes d'écriture. Si l'un de ces termes apparaît
dans la question, la réponse est « base de données ».

**Puis une similarité d'embeddings**, avec le modèle déjà embarqué pour la
recherche, entre la question et une description de chaque catégorie.

| Montage | Sur tout le jeu | Hors questions hors corpus |
| --- | --- | --- |
| Embeddings seuls, descriptions en définitions | 33/54 | non mesure |
| Embeddings seuls, descriptions en **exemples** | 41/54 | 38/46 |
| + vocabulaire déclaré | 44/54 | 41/46 |
| **+ listes d'intention** | **47/54** | **44/46** |

**Deux enseignements de ce tableau.** D'abord, rédiger les descriptions comme
des **phrases d'exemple** plutôt que comme des définitions de catégorie fait
gagner 8 points : un modèle de phrases rapproche une question d'un texte qui lui
ressemble, pas d'une étiquette abstraite. Ensuite, un vocabulaire **déclaré**
bat un modèle sur son propre terrain quand le vocabulaire est celui du domaine.

**Piège de terminologie sur les termes en plusieurs mots.** Mon croisement se
faisait sur des **mots isolés**, donc « prix d'achat » n'était jamais reconnu :
ce n'est ni « prix » ni « achat ». Neuf termes de mon vocabulaire étaient dans
ce cas. Traitez les expressions par recherche de sous-chaîne.

## 12.4 Le chiffre qui compte plus que la moyenne

**9 sur 9** sur les questions qui **démontrent une exigence**, contre 2 sur 6
avec les embeddings seuls.

**Pourquoi ce chiffre pèse plus que l'agrégat.** Mal routée, « quelle est la
marge sur la REF-8842 ? » ne déclencherait **jamais** le refus de colonne, et E5
deviendrait invisible dans la conversation. Une exigence qui cesse d'être
démontrable est un dommage bien plus grave que trois points de moyenne.

**À faire :** listez ces questions à part, et faites échouer votre mesure si
l'une d'elles est mal routée.

## 12.5 Composer la réponse sans inventer

**À faire :** ne reformulez **rien**. Rendre 27 sous la forme « il y a eu 27
commandes en avril » demanderait une génération par-dessus une donnée juste,
donc une occasion d'inventer là où il n'y en avait aucune.

**Utilisez des gabarits déterministes :**

| Cas | Réponse |
| --- | --- |
| une ligne, une colonne | la **valeur seule** |
| une ligne, plusieurs colonnes | les paires nom-valeur |
| plusieurs lignes | le nombre, plus le tableau |
| aucune ligne | « aucun résultat » |
| identifiant absent | « aucune donnée pour cet identifiant » |

**Deux défauts qu'un relecteur a vus sur une capture d'écran, et pas moi.** Mon
gabarit scalaire recopiait le **nom de colonne du SQL** dans une phrase destinée
à un humain : il affichait `COUNT(*) : 28` au lieu de `28`. Personne ne demande
« combien de commandes en mai ? » pour lire `COUNT(*)`. Et un tableau d'une
seule cellule répétait la valeur déjà donnée.

Faites relire vos écrans par quelqu'un d'autre. Vous ne voyez plus ce que vous
avez écrit.

## 12.6 La trace du routage n'est pas le journal

**Piège conceptuel, et je m'étais trompé.** J'avais annoncé que la décision de
routage irait au journal. C'est faux : le journal est l'**artefact d'audit** de
la direction informatique, dont le contrat fixe les clés. Y verser nos
étiquettes le ferait sortir du contrat.

**À faire :** le client tient sa **propre** trace, qui dit **pourquoi** tel
outil a été appelé, là où le journal dit **que** tel outil a été appelé et avec
quelle issue. Deux fichiers, deux responsabilités.

## 12.7 Le sélecteur de profil, et quand il est légitime

J'ai refusé un sélecteur pour l'interface livrable, puis j'en ai ajouté un pour
l'assistant, à la demande du pilote. Ce n'est pas une contradiction, et voici
la ligne exacte :

| | Ce que c'est | Verdict |
| --- | --- | --- |
| Le profil comme **paramètre d'appel d'outil** | rempli par l'appelant, donc falsifiable | **jamais** |
| Un sélecteur qui choisit **à quel serveur on parle** | deux processus tournent, chacun avec son profil figé | acceptable |

Dans le second cas, aucun outil ne reçoit de profil, aucune variable
d'environnement ne bouge, et le sélecteur choisit un **interlocuteur**. Le fil
de conversation peut alors être commun, chaque réponse portant la marque du
profil qui l'a produite, avec un bouton qui rejoue la même question sur l'autre
serveur, sans la ressaisir donc sans risque qu'elle diffère d'une virgule.

## 12.8 Choisir les questions d'amorce sur mesure, et non sur ce qu'on espère

**À faire :** si vous proposez des questions en un clic, **jouez-les** d'abord
et écrivez le libellé d'après ce qui se produit **réellement**.

Trois relevés ont changé ma liste :

**La marge.** Les **deux** profils refusent : le support par la table de droits,
le commercial parce que le générateur échoue. Le libellé le dit donc : deux
refus, deux causes, deux codes.

**« Combien de ventes en avril ? » retirée.** Le support rend un résultat, la
table des ventes lui étant cachée le modèle substitue une autre table en
silence, tandis que le commercial échoue. Le bouton donnerait à croire que le
support a **plus** d'accès que le commercial, l'inverse de la vérité.

**« Supprime les commandes de test ».** Sur le profil commercial, le modèle
produit un **vrai** `DELETE` que la couche d'analyse arrête. C'est la meilleure
démonstration de E3 du projet, et elle était invisible.

**Leçon :** un bouton de démonstration qui promet plus que ce que le système
rend est le pire des défauts sur un écran, parce que l'évaluateur clique.
# 13. Le bot de messagerie

## 13.1 Ce que c'est vraiment

**Piège de conception, et il traînait dans mon dossier depuis des jours.** Le
bot de messagerie n'apparaissait que comme une **étiquette** : une boîte dans un
schéma, une ligne dans un tableau. Neuf mentions, toutes décoratives.

Or c'est un **programme à héberger**, et le véritable appelant du serveur :

```
  l agent  ->  la messagerie  ->  CE service  ->  le serveur  ->  recherche / base
```

## 13.2 Quatre contraintes, et la quatrième n'était pas dans mon dossier

**Le budget de trois secondes.** La messagerie attend un accusé de réception
quasi immédiat. Or notre chaîne le dépasse largement : la recherche coûte
quelques secondes, la génération SQL une quinzaine.

**À faire :** répondez `200` **tout de suite**, publiez un accusé de réception,
puis envoyez la réponse dans un **second message**. Ce n'est pas un détail
d'implémentation : cela change le contrat d'interaction, et il faut le dire à
l'utilisateur qui attend.

Mesure obtenue : le `200` revient en **1 milliseconde** en local, et environ 90
millisecondes depuis l'extérieur.

**Un point d'entrée public.** La messagerie pousse ses événements vers une URL
joignable depuis l'extérieur. C'est une unité déployée à part entière, avec sa
propre surface d'exposition.

**Une signature à vérifier.** C'est la **seule frontière de confiance** du
service : sans elle, n'importe qui peut lui faire croire qu'un message vient de
la messagerie, et donc lui faire appeler le serveur.

**Les nouvelles tentatives, absentes de mon dossier.** Sans `200` dans le
budget, la messagerie **rejoue** l'événement, jusqu'à trois fois. Sans
déduplication, la même question partirait trois fois au serveur, et le journal
porterait **trois appels pour une question**.

**À faire :** mémorisez les identifiants d'événements déjà traités, dans un
ensemble borné.

## 13.3 La vérification de signature, dans le détail

**À faire :** relevez la spécification à la source. Pour la messagerie utilisée
ici, elle dit :

| Point | Valeur |
| --- | --- |
| En-têtes | signature et horodatage, **insensibles à la casse** |
| Chaîne de base | `v0:` + horodatage + `:` + **corps brut** |
| Algorithme | HMAC-SHA256, clé = le secret de signature |
| Préfixe du résultat | `v0=` |
| Fenêtre de rejeu | **cinq minutes** |
| Comparaison | **à temps constant** |

**Piège du corps brut, et il est classique.** La signature porte sur les
**octets reçus**. Si vous analysez le JSON puis le resérialisez pour le signer,
les espaces changent et la vérification échoue **sans que rien n'indique
pourquoi**. Gardez le corps brut.

**Piège de la comparaison.** Une comparaison ordinaire de chaînes s'arrête au
premier caractère différent, ce qui fuit la position de l'erreur et permet de
reconstituer la signature octet par octet. Employez la fonction de comparaison à
temps constant de votre bibliothèque de cryptographie.

**À faire, et c'est important :** si le secret est absent, le service doit
**démarrer et refuser tout**. Un point d'entrée public qui accepterait sans
vérifier serait pire qu'un service arrêté. Et cela permet de déployer avant que
l'application de messagerie existe, ce qui est nécessaire puisque l'URL doit
exister avant d'être vérifiée.

## 13.4 Ce que la signature prouve, et ce qu'elle ne prouve pas

Elle prouve que la requête vient de l'application qui partage ce secret, et
qu'elle est récente.

Elle ne prouve **rien sur la personne** qui a écrit le message. Cette identité
est **attestée par le bot**, pas vérifiée par le serveur.

**Donc :** cette identité va au **journal**, marquée comme attestée et non
vérifiée, et **jamais** dans une décision d'autorisation. Le bot sait qui
parle ; le serveur ne le sait pas, et n'a pas à le savoir.

L'imputabilité gagne un cran sans que l'autorisation change : le journal peut
porter « qui », tout en continuant de décider sur « quel profil ».

## 13.5 Le format des messages

C'est une exigence à part entière : E1 demande des sources **citées**, et un
message mal conçu les rend illisibles. Un mur de texte où titre, référence et
date se noient satisfait la lettre et rate l'intention.

**Trois règles :**

**Les sources sont une liste, pas une phrase.** Titre en gras, référence en
police à chasse fixe, date en clair. Un agent doit pouvoir dire à un client
« c'est dans la fiche REF-8842 du 12 mars » sans relire trois fois.

**Un refus s'affiche comme un refus**, avec son code. Une messagerie rend le
texte sur fond ordinaire : sans marque explicite, un refus de colonne sensible
ressemble à une réponse.

**Le SQL n'apparaît que sur un refus.** Un agent du service client ne lit pas de
SQL. Mais un refus sans sa requête n'est pas auditable, et c'est là que le SQL
compte le plus.

**Piège de troncature.** Les messageries tronquent les blocs de texte au-delà
d'une certaine longueur, **en silence**. Coupez vous-même, et dites-le.

## 13.6 Deux canaux, deux bots, et pourquoi deux canaux ne suffisent pas

Vous voudrez naturellement un canal par équipe. C'est une bonne idée, et pour
une raison forte : cela déplace l'autorisation vers l'**appartenance au canal**,
contrôlée par la messagerie. Vous cessez de fabriquer le contrôle d'accès et
vous appuyez sur un système dont c'est le métier.

**Mais deux canaux seuls ne suffisent pas.** Un processus porte **un** profil.
Deux canaux qui parleraient au même service obtiendraient tous deux le même
profil, et **leurs noms mentiraient**, ce qui est pire qu'un canal unique, car
un nom qui promet des droits qu'il ne donne pas trompe l'utilisateur.

**À faire :** deux services, chacun lancé avec son profil, et **deux
applications de messagerie**, puisqu'une application n'a qu'une seule URL
d'événements. Puis un seul bot par canal.

| Canal | Bot, et lui seul | Ce qu'il obtient |
| --- | --- | --- |
| équipe support | le bot support | 7 outils, marges et notes internes refusées |
| équipe commerciale | le bot commercial | 8 outils, marges et notes accessibles |

**L'option écartée, et le motif.** Un service unique qui aiguillerait selon le
canal. L'identifiant de canal est certes attesté par la signature, mais il vient
du **contenu de la requête**, ce que notre décision fondatrice a été écrite pour
empêcher. L'isolation deviendrait une propriété de votre code au lieu d'une
propriété du déploiement. Sur un projet dont le sujet est la gouvernance,
c'est un mauvais échange.

## 13.7 Le manifeste, et l'ordre imposé

**À faire :** créez l'application depuis un **manifeste**, un fichier de
configuration que vous collez. Cela évite une dizaine de clics et rend la
configuration reproductible.

**Piège, et j'avais écrit le contraire sans vérifier.** Le manifeste ne peut
**pas** déclarer d'abonnement aux événements sans fournir l'URL. Et fournir
l'URL dès la création ne marche pas davantage, car la messagerie la **vérifie**
en y envoyant un défi, que le service ne sait relever qu'une fois son secret
posé.

**L'ordre est donc contraint par la messagerie**, et non une préférence :

1. créer l'application depuis un manifeste **sans abonnement** ;
2. l'installer, ce qui produit le jeton du bot ;
3. relever le secret de signature ;
4. poser les deux secrets sur le service ;
5. **seulement alors**, activer les événements et coller l'URL ;
6. ajouter l'événement de mention, et enregistrer.

**Ne demandez que les autorisations nécessaires :** entendre qu'on l'appelle, et
répondre. Deux autorisations. Une autorisation demandée « au cas où » est une
surface d'exposition offerte, sur un client tourné vers l'extérieur.

## 13.8 Deux pièges d'usage, vus en direct

**La mention doit être une vraie mention.** Si l'utilisateur tape le nom du bot
comme du texte, ou dans un bloc de code, la messagerie **n'envoie aucun
événement**. Une vraie mention s'affiche comme une pastille cliquable. Dites-le
dans votre mode d'emploi, cela m'a coûté deux diagnostics.

**Le bot doit être membre du canal.** Ajoutez-le par les réglages du canal
plutôt que par une commande, plus fiable.

---

# 14. Déployer

## 14.1 Ce que le brief demande, et ce qu'il n'impose pas

Le brief demande **un lien vers une interface déployée**. Il n'impose **aucun**
hébergeur. Tenez cette nuance : vous choisissez, vous justifiez.

**À faire, et c'était un critère de fin de lot que j'avais d'abord négligé :**
**éprouvez la chaîne de déploiement à vide, très tôt**, en déployant une image
d'exemple. Cela valide l'authentification, le groupe de ressources, le registre,
l'environnement et l'entrée publique en quelques minutes, **avant** d'y envoyer
plusieurs gigaoctets.

C'est ce qui m'a révélé que je n'avais pas le droit de créer un groupe de
ressources.

## 14.2 Construire sans moteur local

Si la virtualisation est bloquée sur votre poste, vous ne pouvez pas construire
d'image en local. Ce n'est **pas** bloquant : les registres de conteneurs
savent construire **côté serveur**. Vous téléversez le contexte, ils
construisent.

**À faire :** un fichier d'exclusion du contexte, faute de quoi vous enverriez
votre environnement virtuel et votre cache de modèles. Mesure : contexte ramené
à **10,4 Mo**, contre 1,3 Go d'environnement et 4,8 Go de cache laissés sur le
poste.

## 14.3 Cinq échecs de construction, et aucun là où je l'attendais

J'avais écrit en tête de mon fichier de construction quelle étape était la plus
fragile. **Elle n'a jamais échoué.** Voici celles qui ont cassé.

**Échec 1 : l'analyseur du registre n'est pas celui de Docker.** J'avais mis du
code Python en ligne dans le fichier de construction, avec la syntaxe des
documents-ci-joints. L'analyse de dépendances du registre ne la comprend pas et
lisait mes lignes Python comme des instructions de construction.

**Parade :** mettez les scripts dans des **fichiers**, et copiez-les.

**Échec 2 : le client en ligne de commande s'est écrasé en affichant les
journaux.** Erreur d'encodage : la console était dans un jeu de caractères
ancien et l'outil de dépendances émet des symboles Unicode.

**Le point important :** la construction se poursuivait **côté serveur**. Seul
l'**affichage** était mort, et mon script s'arrêtait donc sur un succès.

**Parade :** forcez l'encodage de sortie, et surtout n'affichez pas les journaux
pendant l'attente. **Un affichage mort n'est pas une construction morte.**

**Échec 3 : l'image pesait 12,6 Go**, contre un plafond de 10,7 Go sur le
niveau de service choisi pour le registre. Quota dépassé, et le service de
conteneurs rendait une erreur d'**autorisation** qui ne disait rien de la vraie
cause. J'ai perdu du temps à soupçonner les identifiants, jusqu'à prouver par un
appel direct qu'ils fonctionnaient.

**La cause :** le fichier de verrouillage épingle la version de la bibliothèque
de calcul qui embarque les pilotes de carte graphique, quinze paquets. Ma
réinstallation en version processeur remplaçait **la bibliothèque seule** et
laissait les quinze paquets. **L'étape avait fait la moitié du travail, ce qui
est plus sournois qu'un échec franc.**

**Échec 4 : ma correction a aggravé le problème.** Purger les paquets inutiles
dans une **étape séparée** a donné **14,8 Go**, plus gros qu'avant.

**Pourquoi :** les couches d'une image sont **additives**. Retirer des fichiers
dans une couche ultérieure n'efface pas la couche qui les avait ajoutés : cela
empile un masque par-dessus.

| Tentative | Taille |
| --- | --- |
| Sans purge | 12,6 Go |
| Purge en couche séparée | **14,8 Go** |
| **Installation, remplacement et purge dans la même couche** | **6,2 Go** |

**Piège dans le piège :** une synchronisation des dépendances **après** la purge
aurait **réinstallé** les paquets, en réconciliant avec le fichier de
verrouillage, et annulé la purge **en silence**. Installez le projet sans
toucher aux dépendances.

**Et faites relever la liste plutôt que de la recopier :** un script qui liste
les paquets installés et retire ceux dont le nom commence par le préfixe voulu,
puis **échoue** s'il en reste un. Une liste figée dériverait au premier
changement de dépendances et l'image regonflerait sans que rien ne le signale.

**Échec 5 : une variable d'environnement corrompue par le shell.** J'ai passé un
chemin POSIX en argument depuis un shell qui les convertit, et le conteneur a
reçu un chemin Windows. L'application démarrait, servait ses pages, et échouait
à la première question documentaire avec une erreur de collection introuvable
qui ne disait rien de la cause.

**Or le fichier de construction posait déjà ces variables correctement.** Les
repasser était une **redondance qui n'apportait rien et a tout cassé**.

**Leçon générale :** une redondance inutile n'est pas neutre, c'est un risque
pur.

## 14.4 Les secrets, et la panne la plus muette du projet

**À faire :** ne passez **jamais** un secret en argument de ligne de commande.
Il finirait dans l'historique du shell et dans les journaux d'audit. Utilisez le
magasin de secrets de votre hébergeur, puis référencez le secret depuis la
variable d'environnement.

**Trois pièges, et le troisième a coûté une heure.**

**Poser un secret ne suffit pas, il faut le brancher.** Le mettre au magasin ne
le rend pas visible du conteneur : il faut encore déclarer la variable
d'environnement qui le référence. J'avais donné cette commande pour le premier
service et l'avais **omise** pour le second.

**Redémarrer ne prend pas un nouveau secret.** L'outil affiche pourtant « doit
être redémarré pour que le changement prenne effet ». Or la valeur est résolue à
la **création** de la révision. Il faut donc en créer une nouvelle.

**Une nouvelle révision reçoit tout le trafic avant d'être saine.** Pendant le
téléchargement de l'image, c'est l'**ancienne** réplique qui répond : l'ancien
secret marche encore et le nouveau paraît refusé. J'ai failli conclure à tort
**deux fois**.

**Et le piège final, invisible.** Le service refusait tout avec une erreur
d'authentification, alors que le jeton était valide et que le magasin le
contenait. La différence tenait à **un octet** :

| Mesure | Valeur |
| --- | --- |
| Longueur affichée par l'outil en ligne de commande | 59 |
| Longueur vue par le conteneur | **60** |

L'affichage **rogne les espaces de fin**. La valeur stockée portait donc un
retour chariot invisible, ramassé au copier-coller depuis un navigateur. L'outil
me montrait une valeur propre, et le conteneur en avait une autre.

**Ce qui a tranché** n'est ni le journal ni l'outil, mais un **comptage
d'octets à l'intérieur du conteneur**. Un comptage est immunisé contre les
artefacts d'affichage, là où mon premier essai avait cru lire un caractère qui
n'existait pas, et où j'avais bâti un raisonnement dessus avant de voir que
**n'importe quel** jeton erroné produit la même erreur, donc que ce test ne
distinguait rien.

**Parade définitive :** coupez les espaces de bord de tout secret à la lecture.
Un secret ne contient jamais d'espace en tête ni en queue, donc c'est sans
risque, et cela supprime une classe entière de pannes muettes. Et ajoutez un
contrôle **en négatif** : un secret réellement différent d'un caractère doit
rester refusé, sinon votre nettoyage serait trop large.

## 14.5 Tracer les succès, pas seulement les échecs

**Piège méthodologique.** Mon service ne traçait que ses échecs de publication.
Quand l'échec a cessé, il ne restait **rien** dans le journal, et il fallait
déduire la réussite d'une **absence d'erreur**. Ce n'est pas une preuve, c'est
une conjecture confortable.

**À faire :** tracez aussi les succès. Une ligne suffit.

## 14.6 Vos droits réels, à relever avant de coder le script

**À faire :** relevez vos autorisations, en lecture seule, et faites-en un mode
de votre script de déploiement.

Mes droits réels ont imposé une réécriture complète :

| Ce que le script faisait | Ce qu'il doit faire |
| --- | --- |
| créer le groupe de ressources | **vérifier** qu'un groupe existant est là |
| enregistrer les fournisseurs de ressources | **vérifier** leur enregistrement, et dire quoi demander à l'administrateur |
| supprimer le groupe pour tout nettoyer | supprimer **seulement nos ressources**, nommément, car le groupe est partagé |

Les deux premières auraient échoué à la première commande, car mon compte
n'avait qu'un droit de lecture sur l'abonnement.

## 14.7 Les deux choix de dimensionnement qui coûtent

**Une réplique au minimum.** Avec zéro, le service s'éteint au repos, et le
réveil suppose de télécharger une image de plusieurs gigaoctets puis de charger
les modèles : plusieurs minutes de page muette pour qui clique. Une réplique
allumée est facturée en continu. C'est un arbitrage, écrivez-le.

**Une réplique au maximum.** Parce que le journal est un fichier **local au
conteneur** : deux répliques tiendraient deux journaux différents, et l'écran
« journal partagé » cesserait de dire vrai. Passer à l'échelle demanderait un
stockage partagé.

**Piège de dimensionnement mémoire, et c'est ma faute la plus coûteuse.** J'ai
fixé la mémoire d'un service d'après la mesure d'un **autre** service, sans voir
que celui-ci ne chargeait pas le générateur SQL.

| Modèle | Empreinte |
| --- | --- |
| Générateur SQL en précision simple | ~2,0 Gio |
| Modèle d'embeddings | ~0,5 Gio |
| Modèle de reclassement | ~0,5 Gio |

Soit trois gigaoctets, exactement ce que j'avais alloué. La mémoire a saturé à
**100 %**, et le noyau a tué le **sous-processus** serveur sans tuer le
conteneur : **zéro redémarrage au compteur**, et un tuyau de communication
fermé. Le symptôme était une erreur de transport, très loin de la cause.

**Deux leçons :** n'extrapolez pas une mesure d'un service à un autre qui ne
charge pas les mêmes choses ; et regardez le compteur de redémarrages **et** la
mémoire, car un sous-processus tué ne compte pas comme un redémarrage.

## 14.8 Chiffrer le coût, et le calculer plutôt que l'écrire

**À faire :** écrivez un script qui interroge l'**interface tarifaire publique**
de votre hébergeur et la **consommation réelle** de vos conteneurs.

**Pourquoi un script.** Un chiffre recopié dans un document dérive au premier
changement de tarif ou de dimensionnement.

**Deux pièges rencontrés.**

L'interface tarifaire renvoyait **zéro** pour les compteurs de calcul dans une
devise, sur **toutes** les régions, et des valeurs réelles dans une autre.
Publier un coût nul aurait été pire que ne rien publier. Vérifiez vos données
avant de les croire.

Et le tarif « au repos », plus avantageux, ne s'applique que sous des conditions
précises : moins d'un centième de cœur de processeur et moins de mille octets
par seconde de trafic. Mesure de mon conteneur : **treize fois** au-dessus du
seuil. C'est donc le tarif plein qui s'applique, et c'est la borne haute qu'il
faut annoncer.

**Publiez les deux bornes**, et dites laquelle s'applique et pourquoi.

---

# 15. Le catalogue des pièges

Une page à relire avant chaque étape. Chacun de ces pièges a été payé.

## 15.1 Ceux qui ne produisent aucune erreur

Les plus dangereux, parce qu'un test qui passe ne prouve rien.

| Piège | Symptôme | Parade |
| --- | --- | --- |
| Titre non reporté dans les morceaux | citation **fausse** mais bien formée | reporter titre, référence, version |
| Valeur recopiée sans son accent | requête rendant **zéro ligne sans erreur** | relever, jamais recopier |
| Contrôle comparant un fichier à lui-même | tous les contrôles au vert | ancrer les invariants **hors** du fichier |
| Recherche approchée non déterministe | mesures qui se contredisent | effort de recherche élevé, départage déterministe |
| Colonne ajoutée hors classification | **publique par omission** | classification **exhaustive** |
| Substitution silencieuse de colonne | réponse plausible et **hors sujet** | refus explicite déclaré, et le dire |
| Secret avec un caractère invisible | erreur d'authentification inexplicable | couper les bords, compter les octets |

## 15.2 Ceux qui trompent le diagnostic

| Piège | Ce qu'on croit | Ce qui est vrai |
| --- | --- | --- |
| Message de confirmation après un tube | l'opération a réussi | le code de retour a été masqué |
| Code 200 sur un port | l'application fonctionne | le serveur écoute, le code ne s'exécute pas |
| Affichage de journaux qui s'écrase | la construction a échoué | elle continue côté serveur |
| Nouvelle révision avec tout le trafic | elle répond | l'ancienne répond encore |
| Zéro redémarrage au compteur | rien n'est mort | un sous-processus a été tué |
| Sortie d'un terminal distant | c'est la valeur | c'est la valeur plus des artefacts |
| Erreur d'autorisation d'un registre | les identifiants sont faux | le quota est dépassé |

## 15.3 Ceux de conception

| Piège | Pourquoi c'est grave |
| --- | --- |
| Le profil en paramètre d'outil | l'appelant se déclare ce qu'il veut ; l'exigence devient décorative |
| Le périmètre sur les colonnes **affichées** | un tri ou un filtre divulgue sans afficher |
| Une seule barrière de lecture seule | elle se contourne ; il en faut plusieurs, indépendantes |
| Propager le texte libre du modèle | il invente une règle qui n'existe pas |
| Encoder les droits deux fois | la seconde copie dérive, et une divergence de droits **s'exploite** |
| Aligner un test sur le comportement observé | une limite devient un comportement attendu, et disparaît |
| Nommer un canal d'après des droits qu'il n'a pas | le nom ment, et l'utilisateur le croit |

## 15.4 Ceux d'outillage

| Piège | Parade |
| --- | --- |
| Documents-ci-joints qui mangent antislashs et accents graves | écrire le code dans un fichier |
| Continuation de ligne différente selon le shell | commandes sur une seule ligne |
| Conversion automatique des chemins | désactiver la conversion, ou chemins relatifs |
| Couches d'image additives | tout faire dans **une** couche |
| Synchronisation qui réinstalle ce qu'on a purgé | installer sans toucher aux dépendances |
| Réglage de page appelé deux fois | utilitaire tolérant au second appel |
| Session serveur morte et jamais rouverte | détecter et rouvrir une fois |

---

# 16. Plan de travail

Voici l'ordre qui marche, avec le critère qui dit qu'une étape est finie. Les
durées supposent un travail à temps plein et une découverte des sujets.

## Jour 1 : cadrer et préparer

- lire le brief, en extraire les exigences numérotées ;
- monter l'environnement, résoudre les blocages du poste ;
- **relever** le jeu de données par un script ;
- constituer les deux jeux de questions et le fichier d'attendus ;
- lancer la suite de tests fournie et **noter le point de départ chiffré**.

**Fini quand :** la suite de tests échoue pour une seule raison claire, du genre
« module introuvable », et que vous connaissez le nombre exact d'échecs.

## Jour 2 : la table de droits, avant tout le reste

- écrire le fichier unique de droits ;
- écrire le script de vérification, avec les invariants **en dur** ;
- **éprouver chaque contrôle en le faisant échouer**, un par un ;
- générer la vue lisible.

**Fini quand :** dix mutations volontaires produisent dix échecs, chacun nommant
le fautif.

**Pourquoi en premier.** Tout le reste s'appuie sur les droits. Les écrire en
dernier oblige à repasser partout.

## Jour 3 : la recherche documentaire

- les chargeurs par format, vers la forme unique ;
- le découpage, **avec le report du titre** ;
- l'indexation, dense et lexicale ;
- les contrôles d'ingestion, et vérifier la reproductibilité ;
- la recherche hybride, la fusion, le court-circuit des références ;
- le reclassement et les **deux** seuils.

**Fini quand :** une question sur une référence rend **cette** référence en
tête, une question hors corpus rend une abstention, et quatre exécutions rendent
la même liste.

## Jour 4 : l'interrogation de la base

- le schéma borné au profil, avec les valeurs réelles ;
- les six couches, dans l'ordre ;
- une trentaine de cas d'attaque, **tous éprouvés** ;
- le générateur, et sa mesure honnête.

**Fini quand :** aucune écriture ne passe, aucune colonne interdite ne sort même
par un tri ou une sous-requête, et vous avez un chiffre pour la qualité de
génération.

## Jour 5 : le serveur

- le point de passage unique ;
- le catalogue borné, l'enveloppe, les cinq statuts ;
- le journal ;
- le préchauffage, **imports dans le fil principal** ;
- faire passer la suite de tests du rouge au vert.

**Fini quand :** la suite fournie est verte, et le journal contient une ligne
par appel, refus compris.

## Jour 6 : mesurer, montrer, déployer

- générer le rapport de mesure, avec ses intervalles et ses réserves ;
- générer le guide d'accès ;
- l'interface, cinq écrans, l'écran de comparaison en premier ;
- **éprouver la chaîne de déploiement à vide**, puis déployer ;
- relire tous les documents et **fermer les dérives**.

**Fini quand :** le lien répond, et les six exigences se démontrent en cliquant.

## Ce qui vient après, si le temps le permet

L'assistant conversationnel et le bot de messagerie. Ils ne sont pas au brief,
et le routeur du premier est le cerveau du second : ce n'est donc qu'un seul
chantier avec deux devantures.

---

# 17. La liste de contrôle finale

À passer avant de rendre. Chaque ligne se vérifie en une commande ou un clic.

## Les exigences

- [ ] **E1** : une réponse documentaire cite titre, référence, date
- [ ] **E1** : une question hors corpus rend une **abstention affichée**
- [ ] **E1** : une question sur une référence cite **cette** référence, pas une autre
- [ ] **E2** : une référence exacte remonte en tête
- [ ] **E2** : une question en langage naturel aboutit
- [ ] **E3** : une demande d'écriture est refusée
- [ ] **E3** : la requête est renvoyée avec le résultat
- [ ] **E3** : la requête d'un refus est visible
- [ ] **E4** : les deux profils ont deux catalogues d'outils différents
- [ ] **E4** : un outil interdit rend un refus, pas une erreur technique
- [ ] **E5** : une colonne sensible est refusée au profil restreint
- [ ] **E5** : le refus tient même par un tri ou une sous-requête
- [ ] **E5** : le journal contient **tous** les appels, refus compris
- [ ] **E6** : le rapport de mesure existe, **généré**, avec ses intervalles

## La rigueur

- [ ] aucun fait n'existe à deux endroits sans script de vérification
- [ ] chaque contrôle a été vu **échouer** au moins une fois
- [ ] les invariants sont ancrés **hors** du fichier qu'ils contrôlent
- [ ] la classification des colonnes est **exhaustive**
- [ ] aucun secret dans un fichier suivi par git, **ni dans l'historique**
- [ ] les limites connues sont déclarées, avec leur cause, et **plafonnées**

## Le déployé

- [ ] le lien public répond
- [ ] les modèles sont dans l'image, pas téléchargés au démarrage
- [ ] les chemins d'artefacts passent par une variable unique
- [ ] le coût est **chiffré**, avec la commande d'extinction écrite
- [ ] un point d'entrée public **refuse** une requête non signée

## Le dossier

- [ ] chaque décision porte un statut et un motif
- [ ] les options écartées sont nommées, **avec leur motif**
- [ ] les erreurs commises sont racontées, avec leur cause
- [ ] les chiffres sont accompagnés de ce qu'ils ne prouvent pas

---

# 18. Le mot de la fin

Trois idées à emporter.

**Un projet de gouvernance se juge sur ses refus.** Une réponse juste est
attendue ; un refus juste, expliqué et journalisé, est la preuve que le système
décide au lieu de subir. Passez donc autant de temps sur les refus que sur les
réponses.

**Ce qui est recopié dérive.** Ce n'est pas une opinion mais un constat, payé
quatre fois sur ce projet. Un fait à un seul endroit, généré partout ailleurs,
avec un script qui sait dire que la copie a divergé.

**Une limite énoncée est une force ; la même limite découverte est une faute.**
Vous n'aurez pas un système parfait. Vous pouvez avoir un système dont vous
connaissez exactement les limites, mesurées, avec leur cause. C'est ce qui
distingue un travail d'ingénieur d'une démonstration.
# Annexe A. Les documents à produire

Le dossier de conception est un livrable à part entière. Voici ce qu'il doit
contenir, et pourquoi chaque pièce existe.

## A.1 La liste

| Document | Ce qu'il tranche |
| --- | --- |
| Vue d'ensemble | le schéma global : d'où viennent les données, qui appelle quoi, où se décide un droit |
| Flux et morceaux | le chemin d'un fichier jusqu'à un morceau indexé, et le modèle de données |
| Outils et interrogation de la base | le catalogue, les six couches, la forme des réponses |
| Table d'accès | les profils, les droits, et comment ils s'appliquent |
| Séquences | quelques diagrammes pas à pas, dont **au moins un refus** |
| Catalogue consolidé | un tableau par outil : nom, entrées, sorties, garanties |
| Choix des bases de données | pourquoi ce stockage, et ce qui a été écarté |
| Cible de déploiement | où, comment, à quel coût |
| Ce que l'interface prouve | écran par écran, l'exigence démontrée |
| Protocole de mesure | écrit **avant** l'implémentation |

## A.2 Trois règles de rédaction qui changent la lecture

**Chaque décision porte un statut.** « Validé », « proposé », « à trancher ».
Un lecteur doit savoir ce qui est acté et ce qui est encore ouvert. Un dossier
où tout a l'air décidé ne se relit pas.

**Chaque option écartée est nommée, avec son motif.** C'est ce qui distingue un
dossier d'un mode d'emploi. Et un motif faux se corrige : j'ai deux fois écarté
une option pour une **mauvaise raison**, et j'ai dû réécrire le motif en gardant
la conclusion. Cela m'a appris que recopier un motif sans le vérifier le propage.

**Séparez la règle du relevé.** Une règle est stable ; un chiffre d'instance
change au prochain jeu de données. Mélanger les deux rend le dossier périmé dès
qu'un fichier bouge. Écrivez la règle dans le dossier et le chiffre dans un bloc
généré.

## A.3 Les diagrammes

**À faire :** des diagrammes en texte, dans une syntaxe versionnable, plutôt que
des images. Un diagramme en texte se relit en diff et se corrige sans logiciel.

**À faire aussi :** un script qui **rend** tous les diagrammes en une page
autonome, et qui **valide** leur syntaxe. Sans validation, un diagramme cassé
s'affiche comme un cadre vide ou une erreur, et vous ne le voyez que le jour de
la présentation.

**Piège de validation, et j'y suis tombé deux fois.** Ne cherchez pas un motif
d'erreur dans le fichier de sortie : l'outil de rendu injecte parfois ses
styles d'erreur dans **tous** ses fichiers, valides compris. J'ai ainsi cru
avoir dix-neuf diagrammes cassés alors qu'ils étaient tous bons.

Le signal fiable est le **code de sortie** de l'outil, et le fait qu'il
n'écrive **aucun** fichier sur un diagramme cassé. Calibrez votre détecteur sur
un cas volontairement cassé **avant** de le croire.

**Piège de prévisualisation.** Si votre éditeur n'affiche pas les diagrammes,
cherchez d'abord un **doublon d'extension**, y compris parmi celles **livrées
avec l'éditeur**. J'ai perdu du temps à suspecter mes fichiers, deux fois, alors
que deux extensions revendiquaient le même bloc et que le rendu cassait sans
message. Diagnostic dans l'ordre : la version de l'éditeur et ses extensions
intégrées, puis les extensions installées, puis la console, et **seulement
ensuite** vos fichiers.

**Piège de syntaxe.** Un point-virgule dans le texte d'un message de diagramme
de séquence est pris pour un séparateur, et le diagramme échoue. Employez des
virgules.

## A.4 Les tableaux

**À faire :** des tableaux au format Markdown, qui se rendent partout.

**Piège de conversion, si vous migrez d'un format à un autre.** J'ai converti
46 tableaux d'un format vers l'autre et j'en ai cassé six, dont les deux du
document livrable. Deux défauts de mon convertisseur : il découpait les cellules
sur un séparateur **interne** sans tenir compte des bordures, et il exigeait
deux espaces d'indentation pour détecter une continuation.

Et un cas qui ne se convertit **jamais** automatiquement : un tableau à
**libellé de groupe**, où une première cellule vide signifie une nouvelle ligne
logique et non une continuation. Repérez-les et réécrivez-les à la main.

**Trois pièges d'échappement**, tous rencontrés : échapper les chevrons, sans
quoi une balise disparaît ; échapper les astérisques, sans quoi le texte entre
deux passe en italique ; recoller les mots coupés en fin de ligne, mais **pas**
quand le séparateur est précédé d'une espace.

---

# Annexe B. S'aligner sur le test plutôt que sur son dossier

C'est le chapitre que j'aurais aimé lire au premier jour.

## B.1 Ce qui s'est passé

J'avais rédigé un dossier de conception complet, cohérent, avec ses arbitrages.
Puis j'ai récupéré le dépôt d'exercice fourni, qui contenait une **suite de
tests boîte noire** et une note de cadrage complète.

Ma copie locale de cette note n'était qu'une **paraphrase**, deux fois plus
courte, sans la table de droits ni le contrat d'intégration. C'était la cause
racine de tout ce qui suit.

## B.2 Ce qui était faux dans mon dossier

**Deux droits sur trois étaient inversés.** Je réservais les briques de
recherche à un profil de développeur ; le cadrage les donne au **support**. Et
la suite de tests appelait précisément ces outils **en profil support** : mon
serveur aurait refusé, et le test serait tombé.

**Le contrat avait raison, pour une raison que je n'avais pas vue.** Le brief
nomme le bot du service client comme celui qui cherche mal dans les documents.
Lui rendre une recherche correcte, c'est donc **précisément** lui donner l'outil
de recherche. E1 ne se protège pas en retirant des outils, elle se protège dans
le contrat de sortie de l'outil de réponse.

**Un profil que j'avais inventé n'existait pas.** Deux profils au contrat, pas
trois.

**Une table était retirée en entier**, là où j'affirmais que la restriction ne
portait jamais sur les tables.

**Et tous les noms avaient bougé** : le nom de la variable d'environnement, les
noms de champs, les statuts, les clés du journal, les noms d'arguments.

## B.3 Les deux leçons

**Le fond a tenu, les noms ont bougé.** Les six couches, la défense en
profondeur, le point de passage unique, la fusion des classements : tout cela
était juste. Ce qui était faux, ce sont les **noms** et un droit d'accès sur
deux. Autrement dit, le raisonnement se transporte, le vocabulaire non.

**Une paraphrase n'est pas une source.** J'avais résumé la note de cadrage en
croyant en garder l'essentiel, et j'avais perdu exactement les deux choses qui
faisaient foi : la table de droits et le contrat.

## B.4 Ce qu'il faut faire, dans l'ordre

1. **Récupérez le contrat réel** avant d'écrire une ligne de code : la note de
   cadrage complète, et la suite de tests si elle existe ;
2. **lancez la suite de tests immédiatement** et notez le nombre d'échecs. C'est
   votre point de départ chiffré, et le seul métre qui compte ;
3. **relevez le contrat mot pour mot** : noms de variables, noms de champs,
   statuts admis, clés de journal. Faites-en des constantes ;
4. **recopiez la table de droits du contrat dans vos invariants**, en dur, et
   assumez cette unique recopie : elle existe précisément pour que votre
   transcription ne puisse pas dériver de la source sans que le contrôle tombe ;
5. **alignez votre dossier sur le contrat**, jamais l'inverse, et **consignez
   les écarts** que vous corrigez. Ce sont eux qui vous rappelleront pourquoi tel
   choix est ce qu'il est.

## B.5 Une bonne nouvelle, pour finir

Mes jeux de questions, reconstitués à la main depuis des captures d'écran du
brief, se sont révélés **identiques** aux jeux officiels : trente sur trente et
vingt-quatre sur vingt-quatre, mêmes identifiants et mêmes questions. Et le
corpus local était identique au corpus distant, au fichier et à l'octet.

Un travail soigné sur des données partielles n'est donc pas perdu. C'est le
**vocabulaire** qui doit venir de la source, pas l'effort.

---

# Annexe C. Rendre un document Word depuis un dépôt

Le livrable attendu peut être un document bureautique. Voici comment le produire
sans dépendre d'un poste particulier.

## C.1 Le principe

**À faire :** écrivez le document en **texte** dans le dépôt, et **générez** le
document bureautique par un script.

**Pourquoi.** Le texte se relit en diff, se corrige sans logiciel, et se
versionne. Le document bureautique devient un **artefact régénérable**, jamais
édité à la main. C'est la même règle que partout ailleurs : ce qui est recopié
dérive.

## C.2 Quand les outils habituels sont bloqués

Sur mon poste, les deux voies normales étaient fermées : la bibliothèque
courante échoue à l'import parce qu'une de ses dépendances charge une
bibliothèque système que la politique de sécurité refuse, et le convertisseur
universel n'était pas installé.

**La parade :** un document bureautique moderne n'est **rien d'autre qu'une
archive compressée de fichiers XML**. Les modules d'archivage et de XML de la
bibliothèque standard suffisent donc, sans aucune dépendance, sans bibliothèque
système, et sans rien demander à l'administrateur du poste.

Les parties minimales à écrire sont peu nombreuses : la déclaration des types de
contenu, les relations, le corps du document, les styles, et la numérotation des
listes.

## C.3 Deux pièges de rendu

**Les espaces de bord sont mangés** si vous ne demandez pas explicitement de les
préserver. Un bloc de code indenté perd alors son alignement.

**Un tableau colle au paragraphe suivant** si vous n'insérez pas un paragraphe
vide après lui.

## C.4 Vérifier avant de livrer

**À faire :** après génération, ouvrez l'archive et vérifiez que **chaque
partie est du XML valide**, puis que les styles attendus sont bien présents dans
le corps. Un document qui s'ouvre à moitié est pire qu'un document absent.
