# Sorabel Data Gateway, reste à faire

> Liste de référence des travaux restants. Elle a compté 34 items le 2026-08-31,
> puis 4 de plus au chantier 7. **Le détail de ce qui a été fait n'est plus
> ici** : il est dans l'historique git, où chaque commit porte son raisonnement.
> Garder les lignes closes ferait de ce fichier un compte rendu, alors que c'est
> une liste de travail.
>
> **A3 et L3 sont fermes le 2026-09-07.** La chaine de deploiement a ete
> eprouvee a vide, puis l'interface a ete deployee et verifiee en production :
> https://sorabel-gateway.mangoplant-5634ed08.francecentral.azurecontainerapps.io
> La demonstration des deux profils a ete jouee DANS le conteneur, 12 entrees
> pour 12 appels. Le brief est **entierement livre**.
>
> Relu le 2026-09-03. Il annonçait encore L1 et L3 comme « bloqués par : le
> serveur n'existe pas encore », trois commits après que le serveur ait fait
> passer la suite d'acceptance de 12 rouges à 12 verts. Même mode de
> défaillance que le guide d'accès et l'oracle de gouvernance, en plus bénin :
> **ce qui n'est pas relu dérive**.

---

## Ce qui reste

| Id | Travail | Fichier | Bloqué par |
| --- | --- | --- | --- |
| A4 | Coût mensuel réel, à établir avec la calculatrice Azure et les volumes du projet | `docs/conception/07_cible_deploiement.md` | rien, mais la décision d'allumer une réplique en continu appartient au pilote |
| A1 | Application Slack : hébergement, vérification de signature, réponse différée en deux messages (D34) | `slack_app/`, à créer | un espace de travail Slack, qui n'existe pas |
| A2 | Format de restitution des sources dans un message Slack. E1 exige des sources citées, un message mal conçu les rend illisibles | à définir | A1 |

---

## Ce qui a changé de nature, et non simplement d'état

Trois items ne se sont pas « faits » : ils ont été **résolus autrement** que la
liste ne le prévoyait. Les laisser ouverts aurait été faux, les cocher aurait
masqué le changement.

**M2, les chiffres de la mesure E6.** Le plan était de remplir à la main le
gabarit de `docs/mesure_e6.md` section 6. Les chiffres existent, mais dans
`eval/rapport_gain.md`, **généré** par `python -m retrieval.rapport`, parce que
c'est ce fichier que la suite d'acceptance de l'amont contrôle. Les recopier
dans le protocole créerait une seconde vérité qui dériverait au premier
réindexage. Le gabarit a donc été remplacé par un renvoi vers le rapport
généré. Reste ouvert, mineur : `eval/results/` est vide, aucune sortie datée
n'est archivée par exécution.

**L1, le client de démonstration montrant deux profils.** Fait, et deux fois :
`scripts/mcp_client.py` est venu du dépôt amont, et
`scripts/demo_deux_profils.py` joue la même séquence de six appels sur les deux
profils par le vrai protocole stdio, avec un journal partagé.

**A1, à moitié.** L'assistant conversationnel a exigé un **routeur** : décider,
depuis une phrase libre, quel tool appeler. C'est exactement le travail du bot
Slack, qui reçoit une phrase et doit faire ce choix. `client/routeur.py` et
`client/conversation.py` sont donc déjà la moitié de A1, la moitié difficile,
et elle est mesurée (`eval/mesure_routage.py`). Ce qui reste propre à Slack est
la **façade** : point d'entrée public, vérification de signature, réponse
différée en deux messages.

---

## L'ordre dans lequel le reste se débloque

```
fait le 2026-09-07  ->  A3 puis L3, la chaine eprouvee puis l'interface en ligne
independant         ->  A4, le cout chiffre
un espace Slack     ->  A1 puis A2
```

**Le brief est entierement livre** : dossier de conception, serveur MCP avec son
guide, suite d'acceptance a 12/12, et l'interface en ligne. Ce qui reste ne
figure pas au brief.

Une reserve qui n'est pas un item de travail mais une decision a prendre :
l'application tourne avec une replique **en continu**, donc facturee en continu,
dans un abonnement de formation partage. Pour l'eteindre sans rien detruire :

```
az containerapp update --name sorabel-gateway \
  --resource-group adialloRG --min-replicas 0
```

---

## Où trouver le reste

```
git log --oneline                  les commits, chacun avec son raisonnement
git log -p docs/RESTE_A_FAIRE.md   l'etat de la liste, jour par jour
MEMOIRE_PROJET.md section 10       le journal d'avancement
```

La phase de conception est close : décisions D1 à D50, arbitrages P1 à P8, plus
aucun point ouvert de conception.
