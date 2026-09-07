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
| Embeddings seuls, descriptions en définitions | 33/54 | — |
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
