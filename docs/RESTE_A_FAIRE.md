# Sorabel Data Gateway, reste à faire

> Liste de référence des travaux restants. Elle a compté 34 items le 2026-08-31,
> puis 4 de plus au chantier 7. **Le détail de ce qui a été fait n'est plus
> ici** : il est dans l'historique git, où chaque commit porte son raisonnement.
> Garder les lignes closes ferait de ce fichier un compte rendu, alors que c'est
> une liste de travail.
>
> **A3 et L3 sont fermes le 2026-09-07.** La chaine de deploiement a ete
> eprouvee a vide, puis l'interface a ete deployee et verifiee en production :
> <https://sorabel-gateway.mangoplant-5634ed08.francecentral.azurecontainerapps.io>
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

Plus aucun item du brief. Trois travaux d'entretien, dont deux sans blocage.

| Travail | Ce qui manque |
| --- | --- |
| `eval/results/` : archiver une sortie datée par exécution de la mesure E6 | Rien ne le bloque. Mineur : le rapport est régénéré, pas archivé. |
| Régénérer les deux secrets Slack, qui ont transité par une conversation | Rien ne le bloque. `Basic Information`, puis `Regenerate`, puis reposer la valeur. |
| Éteindre les trois services après la soutenance | Une décision de date. Les trois commandes sont plus bas et dans le README. |

**A1 est fait et déployé le 2026-09-07**, ce que ce tableau annonçait encore
comme bloqué par un espace de travail inexistant. Deux bots tournent, un par
profil, dans deux canaux distincts : `sorabel-slack` en profil support et
`sorabel-slack-commercial` en profil commercial. L'autorisation est
l'appartenance au canal, contrôlée par Slack.

Deux canaux seuls n'auraient pas suffi : un processus porte **un** profil (D28),
donc deux canaux parlant au même service auraient tous deux obtenu `support`, et
leurs noms auraient **menti**. D'où deux services et deux applications Slack,
une URL d'événements par application. 52 contrôles hors ligne, plus le dialogue
réel désormais éprouvé en production.

**A2 est fait** : `slack_app/formatage.py` rend les sources en liste Block Kit,
titre en gras, référence en code, date en clair, avec un refus marqué comme un
refus et le SQL visible sur un refus seulement. Douze contrôles portent sur ce
seul point, parce qu'E1 exige des sources *lisibles* et non seulement présentes.

**A4 est fait, et calculé plutôt qu'écrit** : `deploy/cout.py` interroge l'API
tarifaire publique d'Azure et la consommation réelle du conteneur. Résultat au
2026-09-07 : **155 USD par mois** au tarif actif, 50 USD au tarif repos, et le
CPU mesuré à 0,127 cœur est **13 fois au-dessus** du seuil de 0,01 qui
conditionne le tarif repos. C'est donc la borne haute qui s'applique. Décision
du pilote : laisser allumé jusqu'à la soutenance.

**`clients.email` est tranchée** : classée `restreinte`, donc fermée au support.
Le motif n'est pas notre préférence mais `docs/schema.sql`, fourni par la DSI,
qui annote la colonne « donnée personnelle : usage interne uniquement ». Un bot
Slack tourné vers l'extérieur n'est pas un usage interne. Reversible en
retirant deux lignes de la matrice.

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

**A1, fait par un détour.** L'assistant conversationnel a exigé un **routeur** :
décider, depuis une phrase libre, quel tool appeler. C'est exactement le travail
du bot Slack, qui reçoit une phrase et doit faire ce même choix.
`client/routeur.py` et `client/conversation.py` étaient donc déjà la moitié
difficile de A1, et elle est mesurée par `eval/mesure_routage.py`. Il n'est
ensuite resté que la **façade** : point d'entrée public, vérification de
signature, réponse différée en deux messages, déduplication des rejeux.

Autrement dit A1 n'a jamais été un chantier séparé de l'assistant : c'était la
même pièce avec une autre devanture, et c'est ce qui l'a rendu faisable en un
après-midi.

---

## L'ordre dans lequel le reste se débloque

```text
fait le 2026-09-07  ->  A3, L3, A4, A2, et A1 ecrite et eprouvee hors ligne
fait le 2026-09-07  ->  A1 deployee, deux bots, un par profil
rien ne bloque      ->  archiver les sorties de mesure, regenerer les secrets
une date            ->  eteindre les trois services
```

**Le brief est entierement livre** : dossier de conception, serveur MCP avec son
guide, suite d'acceptance a 12/12, et l'interface en ligne. Ce qui reste ne
figure pas au brief.

Une reserve qui n'est pas un item de travail mais une decision a prendre :
**trois** services tournent avec une replique en continu, donc factures en
continu, dans un abonnement de formation partage. Environ **465 USD par mois**,
soit **15 USD par jour**, chiffre par `deploy/cout.py`.

Pour les eteindre sans rien detruire, une commande par service, chacune sur une
seule ligne car PowerShell n'accepte pas la continuation par antislash :

```text
az containerapp update --name sorabel-gateway --resource-group adialloRG --min-replicas 0
az containerapp update --name sorabel-slack --resource-group adialloRG --min-replicas 0
az containerapp update --name sorabel-slack-commercial --resource-group adialloRG --min-replicas 0
```

Les rallumer se fait avec `--min-replicas 1`, au prix de quelques minutes de
reveil. Pour tout retirer, `bash deploy/azure.sh --detruire`, qui ne touche pas
au groupe de ressources puisqu'il est partage avec d'autres apprenants.

---

## Où trouver le reste

```text
git log --oneline                  les commits, chacun avec son raisonnement
git log -p docs/RESTE_A_FAIRE.md   l'etat de la liste, jour par jour
MEMOIRE_PROJET.md section 10       le journal d'avancement
```

La phase de conception est close : décisions D1 à D50, arbitrages P1 à P8, plus
aucun point ouvert de conception.
