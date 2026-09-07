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
