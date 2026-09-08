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
