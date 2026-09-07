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
