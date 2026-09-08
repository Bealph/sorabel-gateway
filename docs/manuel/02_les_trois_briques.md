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
