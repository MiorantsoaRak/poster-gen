# Affiche IA — Brief projet

5 novembre 2026 · @Miorantsoa Rakotozafy  
Version révisée après discussion produit et vérification des principales hypothèses.

**Statut : cadrage avant bootstrap.** Ce brief définit une direction de produit à valider. Il ne constitue ni une spécification technique approuvée, ni une autorisation de démarrer l’implémentation. Le prototype mentionné dans le brief initial n’a pas été inspecté dans cette revue.

## Vision

Un service qui transforme « nom du produit + prix + photo » en affiches prêtes à publier, puis permet au commerçant de les ajuster facilement.

**Le problème.** Les boutiques de Tana préparent des publications produit récurrentes : les prix changent, la mise en page varie et les mêmes informations doivent être ressaisies. L’estimation initiale de 20 à 30 minutes par visuel reste à confirmer auprès des boutiques pilotes.

**La solution.** L’IA propose une direction visuelle, intègre le produit dans une scène et prépare les textes. Un éditeur visuel léger permet ensuite de modifier le prix, les textes, le logo et le cadrage. Trois exports sont proposés : feed, carré et story.

**Pour qui.** Original Phone Mada est l’utilisateur zéro. Le pilote pourra ensuite inclure deux ou trois boutiques de téléphonie ou d’électronique à Madagascar. Les autres catégories, dont la mode, seront évaluées après validation de ce premier usage.

**La promesse à tester.** « L’IA prépare mon affiche ; je fais deux ajustements et je publie. » La vitesse compte, mais la fidélité au produit, l’exactitude des informations et la facilité de correction priment. Une nouvelle génération et une simple mise à jour de prix auront des temps de traitement différents.

## Direction retenue pour le cadrage de la V1

**Ne pas faire dépendre la V1 d’un catalogue de templates HTML fixes.** Un prix, un produit ou une intention créative ne doivent pas être limités aux emplacements prévus dans quelques fichiers Jinja2.

La direction recommandée est un **canvas éditable avec une composition proposée par l’IA** :

- une image générée comprenant le produit intégré à sa scène, l’éclairage, les ombres et les éléments décoratifs ;
- des objets éditables pour le titre, le prix, le badge promotionnel, le logo et les coordonnées ;
- une disposition adaptable au produit, au message et au format ;
- des styles de départ facultatifs et la possibilité de décrire une autre ambiance ou de fournir une référence visuelle.

Le fait de conserver quelques objets éditables n’impose pas de template fixe. Le canvas peut enregistrer des positions, dimensions et styles libres. L’interface web pourra naturellement utiliser HTML ; la contrainte concerne le moteur de composition des affiches, pas la technologie d’affichage de l’application.

Le choix d’une bibliothèque d’édition et les règles précises de composition restent à décider après validation des besoins.

## Photo produit : référence et fidélité

GPT Image peut utiliser la photo téléversée comme référence pour intégrer le produit dans une scène cohérente. La photo ne doit donc pas obligatoirement être détourée puis collée sur un fond. Les capacités d’édition à partir de références sont documentées par [OpenAI](https://developers.openai.com/api/docs/guides/image-prompting).

Cette liberté doit rester compatible avec la représentation du produit réellement vendu. Une génération peut modifier une couleur, un bouton, un connecteur, un logo de fabricant ou la disposition des caméras d’un téléphone. Une consigne de préservation ou un masque ne garantit pas une conservation exacte des détails.

Deux traitements sont à évaluer sur les photos du pilote :

| Traitement | Principe | Usage envisagé |
| --- | --- | --- |
| Produit intégré dans une scène | La photo sert de référence à une génération du produit dans son environnement. | Visuels de lancement, mises en scène et promotions. |
| Photo produit préservée | Un détourage conserve la photographie du produit ; la composition et les ombres sont construites autour. | Solution de repli lorsque des détails précis sont altérés ou difficiles à valider. |

Le parcours principal à tester est l’intégration dans la scène. Le second traitement doit permettre de récupérer un résultat fiable sans abandonner la création. Il n’est pas nécessaire d’exposer immédiatement ces choix techniques au commerçant.

Conserver la photo originale et présenter une comparaison avec le résultat avant validation. Le nom exact, le coloris et les caractéristiques confirmées par la boutique restent la source de vérité. L’IA ne doit pas inventer de caractéristiques, de remises, de garanties ou de conditions de livraison.

## Parcours utilisateur

1. **Renseigner le produit.** Importer une photo ou sélectionner un produit enregistré ; confirmer la référence, le coloris, le prix et l’offre.
2. **Donner une intention.** Choisir une ambiance de départ, écrire une consigne ou joindre une référence de style. Les ambiances ne verrouillent pas la mise en page.
3. **Obtenir une proposition.** L’IA prépare la scène produit, une composition et des textes à partir des informations vérifiées.
4. **Ajuster visuellement.** Le commerçant modifie directement le prix, le titre, les couleurs, le logo et le cadrage.
5. **Vérifier.** Comparer le produit à la photo originale et contrôler chaque format de sortie.
6. **Exporter et enregistrer.** Télécharger les visuels et la légende ; conserver la création pour une prochaine offre.

Une création enregistrée doit pouvoir être reprise par « même visuel, nouveau prix ». Une modification du prix seul ne nécessite ni nouvelle image, ni nouvelle rédaction par un modèle.

## Édition et retouches

### Fonctions prioritaires de la V1

| Besoin | Interaction attendue |
| --- | --- |
| Modifier un prix ou une accroche | Toucher ou cliquer le texte, puis saisir la nouvelle valeur. |
| Donner plus de place au prix | Déplacer et redimensionner l’objet, avec repères d’alignement. |
| Ajuster le logo | Déplacer, redimensionner ou remplacer le fichier. |
| Adapter les couleurs et polices | Choisir dans la palette et les polices de la boutique. |
| Améliorer le cadrage | Recadrer ou repositionner l’image de scène. |
| Revenir en arrière | Annuler, rétablir ou restaurer une version antérieure. |

Le produit est intégré à l’image de scène : le déplacer indépendamment de cette scène n’est pas une simple opération de glisser-déposer. Cela demande une retouche générative ou un produit conservé sur un calque distinct. L’interface ne doit pas promettre une indépendance des objets qui n’existe pas.

### Retouche locale par IA, après validation de l’édition de base

Interaction proposée : **sélectionner une zone → décrire la modification → comparer → accepter ou annuler**.

Exemples : supprimer une décoration, éclaircir un fond ou modifier l’ambiance. Les éditions guidées par annotations sont décrites dans le [guide OpenAI](https://developers.openai.com/api/docs/guides/image-prompting).

Chaque retouche conserve la version précédente. Pour une modification strictement locale, l’application pourra recomposer seulement la zone acceptée sur l’image originale afin de préserver les pixels extérieurs. Les raccords et les détails à l’intérieur de la zone devront toujours être vérifiés.

Cette fonction ne doit pas retarder la validation des opérations fréquentes : modifier un prix, agrandir un titre et ajuster un logo.

### Approches à garder en expérimentation

- **Affiche entièrement générée, texte compris.** Utile pour explorer des directions créatives ; moins prévisible pour des corrections exactes et fréquentes.
- **Conversion d’une affiche aplatie en calques.** Canva propose [Magic Layers](https://www.canva.com/magic-layers/) en bêta pour ce type de transformation. Tester des exemples est pertinent ; aucune API intégrable n’a été vérifiée ici. Reconstruire les polices, les fonds cachés et les objets superposés ne fait pas partie du périmètre initial recommandé.

## Chaîne de création et réutilisation

| Étape | Résultat attendu | Réutilisation |
| --- | --- | --- |
| Informations produit et boutique | Référence, prix, caractéristiques confirmées, identité de marque. | Catalogue et préférences de la boutique. |
| Direction créative | Intention, contraintes de composition et textes proposés. | Direction enregistrée et ajustable. |
| Préparation des images | Scène avec produit intégré, ou détourage et fond pour le traitement de repli. | Visuel associé au produit et au coloris concernés. |
| Composition éditable | Image de scène et objets de texte, prix, badges et logo. | Création enregistrée avec ses versions. |
| Déclinaison | Disposition et cadrage propres à chaque format. | Variantes liées à la même création. |
| Validation et export | Images téléchargeables et légende validée. | Historique des sorties. |

Une scène qui contient déjà un produit ne constitue plus un fond générique interchangeable entre produits. Le cache doit distinguer les fonds seuls et les visuels liés à une référence. Un visuel approuvé reste réutilisable pour cette référence lors d’un changement de prix ou d’offre.

Conserver les modifications utilisateur lors des reprises. Un changement de prix dans le catalogue doit signaler les créations concernées ; il ne doit pas écraser silencieusement les versions déjà approuvées ou exportées.

## Architecture et stack : choix actés et pistes à confirmer

**Choix utilisateur du 5 novembre 2026 : toute interface web sera développée avec Vite + Vue, aux côtés d’une API FastAPI.** La bibliothèque canvas devra s’intégrer à cette stack ; son choix reste ouvert.

Les autres choix ci-dessous servent au cadrage. Les contrats d’API, le stockage, les états des traitements et les responsabilités de rendu seront décrits dans le design après approbation des exigences.

| Couche | Choix ou piste | Point à valider |
| --- | --- | --- |
| API | FastAPI, choix acté ; Pydantic pour la validation des données | Contrats d’API et besoins de l’éditeur. |
| Interface web | Vite + Vue, choix acté si une UI est développée | Parcours utilisateur, ergonomie mobile et intégration du canvas. |
| Traitements longs | File de tâches avec Redis et un worker | Reprises, quotas, délais et consommation mémoire mesurés. |
| Base | PostgreSQL, avec documents de composition versionnés si nécessaire | Isolation entre boutiques, historique et compatibilité des versions. |
| Fichiers | Stockage adapté au pilote, puis stockage objet si nécessaire | Originaux, visuels générés, versions, exports et sauvegardes. |
| Texte et composition | Modèle de texte produisant une proposition structurée | Qualité des textes français et malgaches, exactitude et respect des informations fournies. |
| Images | OpenAI Images API, modèle supporté évalué sur les produits réels | Fidélité, coût par résultat accepté et temps de génération. |
| Détourage de repli | Outil spécialisé, par exemple rembg | Qualité des contours et coût réel en ressources. |
| Éditeur visuel | SDK canvas tel que Polotno, ou éditeur ciblé avec Fabric.js | Compatibilité avec Vue, licence, ergonomie mobile, export, historique et effort d’intégration. |
| Rendu final | Export cohérent avec le document canvas | Polices, résolution et concordance entre aperçu et fichier exporté. |
| Déploiement | Frontend Vite + Vue et API FastAPI ; hébergement à dimensionner | Distribution du frontend, concurrence des traitements et sauvegardes. |

[Polotno](https://polotno.com/docs/overview) fournit un éditeur intégrable ; [Fabric.js](https://www.fabricjs.com/) fournit des primitives plus bas niveau. Aucun choix de bibliothèque canvas n’est arrêté dans ce brief. Leur intégration dans Vue sera évaluée avant sélection, sans remettre en question le choix Vite + Vue.

Le prototype `poster-kit.zip`, décrit dans le document initial comme contenant un détourage, un moteur de rendu et deux templates, devra être inspecté avant réutilisation. Ses références visuelles ou composants utiles pourront être conservés sans imposer son moteur HTML à la V1.

### Points de fiabilité à couvrir dans les exigences et le design

- Échec ou délai excessif d’un fournisseur : état visible, brouillon conservé et relance contrôlée.
- Quota épuisé ou image refusée : explication utile et action possible ; pas de boucle de tentatives automatiques.
- Retouche incorrecte : conservation du résultat précédent et possibilité de rejeter la nouvelle version.
- Export incomplet ou texte débordant : signalement avant téléchargement de la série finale.
- Perte de connexion : comportement explicite pour les modifications non enregistrées.
- Plusieurs boutiques : séparation des fichiers, créations et informations de chaque client.

Les règles de reprise, d’authentification, de facturation et de publication devront être détaillées avant l’implémentation des fonctions concernées.

## Modèle de données conceptuel

Le nombre de tables n’est pas fixé à ce stade. Le modèle doit couvrir les responsabilités suivantes sans dépendre d’un fichier HTML par style :

| Entité | Informations principales | Rôle |
| --- | --- | --- |
| Boutique | Nom, logo, couleurs, polices, langue, coordonnées, livraison. | Identité et préférences réutilisables. |
| Produit | Référence, variante, prix en Ariary, photos originales, caractéristiques confirmées. | Source des informations commerciales. |
| Direction visuelle | Ambiance, références, préférences de composition. | Point de départ facultatif, sans grille imposée. |
| Visuel | Image, produit et variante associés si présents, modèle et références utilisés, statut de validation. | Actif visuel réutilisable. |
| Création | Objets éditables, textes, instantané des informations commerciales, versions par format et historique. | Document que le commerçant peut reprendre. |
| Traitement | Type d’opération, progression, résultat, erreur et consommation mesurée. | Suivi des générations, retouches et exports. |

Le catalogue peut évoluer sans modifier rétroactivement une affiche exportée. Les identifiants et accès Facebook n’ont pas à être collectés pour un pilote limité à la création et au téléchargement.

## Directions visuelles et formats

Les styles néon et pastel du brief initial restent de bonnes références de départ. Ils ne constituent pas une liste fermée : studio, lifestyle, minimal ou une ambiance décrite librement doivent pouvoir être explorés.

Les intentions commerciales — promotion, nouveauté, mise en avant d’un bénéfice — orientent la composition. Les comparatifs à plusieurs produits peuvent attendre la validation du parcours à un produit.

| Format de sortie envisagé | Taille | Usage visé |
| --- | --- | --- |
| Feed vertical | 1080 × 1350 | Publications verticales. |
| Carré | 1080 × 1080 | Publications carrées et partage. |
| Story | 1080 × 1920 | Publications plein écran verticales. |

Réutiliser autant que possible le même visuel produit approuvé dans les trois formats, avec un cadrage et une disposition des textes adaptés. Si un format exige une extension ou une nouvelle génération, faire valider cette variante. Vérifier les zones de sécurité selon le placement ciblé ; une marge fixe ne doit pas être présentée comme universelle.

Règles communes : prix lisibles au format « 1 200 000 Ar », coordonnées exactes, identité de la boutique cohérente et absence de texte coupé. La règle historique de rejet au-delà de 20 % de texte a été supprimée ; la quantité de texte doit être guidée par la lisibilité. Voir le [compte rendu de cette suppression](https://www.searchenginejournal.com/facebook-removes-the-20-text-limit-on-ad-images/381844/).

## Périmètre commercial et évolutions

La valeur à vendre est un service récurrent de création pour la boutique : son catalogue, ses prix, son identité et son langage sont déjà connus. La mise en scène produit existe chez d’autres fournisseurs, notamment [Photoroom](https://www.photoroom.com/api/product-staging) ; la différenciation proposée repose sur la simplicité du parcours local et la réduction du travail répétitif.

| Priorité | Fonction | Bénéfice à vérifier |
| --- | --- | --- |
| Pilote | Création depuis une photo, édition directe et trois exports. | Obtenir une affiche publiable avec peu de corrections. |
| Pilote | Produit et identité de boutique enregistrés. | Éviter les saisies répétitives et les variations de marque. |
| Pilote | « Même visuel, nouveau prix » et historique. | Réutiliser rapidement une création approuvée. |
| Après validation de l’édition | Retouche locale par IA. | Corriger une scène sans repartir de zéro. |
| Ensuite | Packs de campagne : prix, bénéfices vérifiés, story et légendes. | Préparer plusieurs publications cohérentes. |
| Ensuite | Français, malgache ou bilingue avec expressions approuvées. | Adapter les textes au public ; validation initiale par un locuteur compétent. |
| Selon la demande | Import Odoo, prix en masse, stock et expiration d’offres. | Maintenir les informations à jour. |
| Plus tard | Publication et planification Facebook, vidéo, marque blanche, veille concurrentielle. | Étendre le service après preuve d’usage récurrent. |

La publication automatique et l’intégration Odoo demandent leur propre étude des accès, erreurs, doublons et contraintes du fournisseur. Les estimations initiales en nombre de jours ou de lignes de code ne sont pas des engagements.

L’alternance de deux publications organiques ne constitue pas un test A/B contrôlé : l’audience, l’horaire et la distribution peuvent différer. Mesurer d’abord les créations approuvées, publiées et réutilisées ; interpréter les différences d’engagement avec prudence.

## Coûts et modèle économique

Le coût doit être mesuré **par création acceptée ou pack livré**, en incluant les images de référence, les générations rejetées, les retouches, les exports, le stockage, l’hébergement et le temps d’assistance. Les hypothèses initiales « moins de 0,05 $ par affiche » et « plus de 90 % de marge nette » ne sont pas validées.

| Poste | Méthode d’estimation |
| --- | --- |
| Texte et proposition de composition | Usage réel du modèle sur des produits représentatifs. |
| Génération et retouches d’images | Coût de toutes les tentatives nécessaires pour obtenir un résultat accepté. |
| Détourage et exports | Ressources et durée mesurées ; un traitement local consomme aussi de l’infrastructure. |
| Stockage et hébergement | Volume des originaux, versions et sorties, avec sauvegardes et concurrence. |
| Assistance | Temps de correction et d’accompagnement par boutique. |

**Modèle d’image.** GPT Image 1.5, cité dans le brief initial, est annoncé en fin de service le **1er décembre 2026**. Évaluer un modèle supporté au moment du développement. La documentation actuelle présente notamment GPT Image 2.6 Flare et Sunburst. Voir les [dépréciations](https://developers.openai.com/api/docs/deprecations) et le [guide des modèles d’image](https://developers.openai.com/api/docs/guides/image-prompting).

**Crédits API.** Les abonnements ChatGPT Pro éligibles peuvent actuellement activer des crédits API couvrant notamment la génération et l’édition d’images. Les crédits mensuels inutilisés expirent à la fin du cycle de facturation. Vérifier l’éligibilité et le solde effectif ; calculer aussi la viabilité sans ce bénéfice. Voir les [conditions du bénéfice API](https://developers.openai.com/api/docs/guides/chatgpt-api-credits).

**Délais.** « Moins d’une minute » reste une cible à mesurer, pas une garantie : OpenAI indique que des requêtes complexes peuvent prendre jusqu’à deux minutes. Les mises à jour sans génération doivent être évaluées séparément. Voir les [limites documentées](https://developers.openai.com/api/docs/guides/image-generation).

### Hypothèses tarifaires à tester

- **À l’unité :** conserver 10 000 Ar pour une création déclinée en trois formats comme point de départ d’entretien commercial.
- **Abonnement boutique :** tester l’hypothèse de 150 000 Ar par mois pour 40 créations ; définir le nombre de nouvelles scènes, les retouches incluses et les limites de révision. La publication automatique n’est pas incluse dans le pilote envisagé.
- **Agence :** conserver l’idée d’une offre à 400 000 Ar comme hypothèse future, une fois les besoins multi-boutiques, de marque blanche et d’intégration vérifiés.

Préciser ce qui compte comme une création, une retouche, un format supplémentaire ou un simple changement de prix avant de fixer les quotas. Aucun gain de marge n’est établi à ce stade.

## Validation et plan de progression

### Étape actuelle — valider le brief

Confirmer le périmètre du pilote et la direction sans templates HTML fixes. Aucun bootstrap, dépôt ou développement n’est lancé par cette mise à jour.

### Prochaine étape, uniquement sur demande — bootstrap et exigences

Suivre l’accord de travail : bootstrap du projet, validation de `PROJECT.md`, puis exigences par fonctionnalité avec critères d’acceptation, design, tâches et implémentation. Le brief et les références visuelles alimenteront ces documents ; le prototype sera inspecté avant toute décision de réutilisation.

### Pilote produit envisagé

Tester environ 20 produits représentatifs avec Original Phone Mada, puis quelques boutiques supplémentaires. Inclure des photos imparfaites et des références dont les détails sont faciles à confondre.

Exercice central : demander au commerçant de modifier le prix, d’agrandir le titre et de demander une correction visuelle. Observer les difficultés sans présumer qu’une interface plus complète serait meilleure.

Mesurer :

- taux d’acceptation au premier essai et nombre de reprises ;
- erreurs dans l’apparence du produit et les informations commerciales ;
- temps de correction et capacité à utiliser l’éditeur sans aide ;
- coût par création acceptée ;
- proportion de créations effectivement publiées ;
- réutilisation des produits enregistrés et volonté de payer ou de renouveler.

Définir les seuils de réussite avant le pilote, à partir d’une première observation du travail actuel. Les prochaines fonctions seront choisies selon les difficultés mesurées : fidélité des images, édition, réutilisation ou publication.

## Questions ouvertes avant bootstrap

- [ ] **Pilote et périmètre.** Outil pour une seule boutique au départ ou pilote avec plusieurs boutiques ? Quels besoins d’accès et de séparation en découlent ?
- [ ] **Édition.** Valider le canvas léger et les cinq opérations essentielles : texte/prix, déplacement/redimensionnement, couleurs/polices, cadrage, annulation/export.
- [ ] **Photos.** Quelles sources et variantes seront disponibles ? Sur quels produits l’intégration générative doit-elle être comparée au traitement qui préserve la photo ?
- [ ] **Usage réel.** Téléphone, ordinateur ou les deux ? Quelles contraintes de connexion et quelles langues sont prioritaires ?
- [ ] **Critères de réussite.** Quel temps de correction, quel coût et quel niveau de fidélité rendent le service utile et vendable ?
- [ ] **Éditeur.** Quelle bibliothèque compatible avec Vite + Vue offre le bon compromis entre licence, effort d’intégration et développement ciblé ?
- [ ] **Modèles et budget.** Quels modèles sont accessibles, quels crédits sont activés et quel plafond de dépense retenir ?
- [ ] **Hébergement.** Choisir après mesure des besoins de l’éditeur, des traitements et du stockage ; ne pas reprendre une capacité supposée du prototype.
- [ ] **Tarification.** Création à l’unité ou pack de campagne ? Quelles retouches et mises à jour sont incluses ?
- [ ] **Nom du projet.** Confirmer le nom de travail avant de rechercher une disponibilité de domaine et de dépôt.

## Historique de cette révision

- Choix utilisateur du 5 novembre 2026 : Vite + Vue pour toute interface web, avec FastAPI côté API ; bibliothèque canvas encore à sélectionner.
- Remplacement de la dépendance aux templates HTML par une direction de composition libre dans un canvas éditable.
- Intégration du produit dans la scène à partir d’une photo de référence, avec validation de fidélité et traitement de repli.
- Ajout du parcours d’édition, de l’historique et de la retouche locale progressive.
- Clarification des limites : produit intégré non déplaçable indépendamment, cache lié à la référence et validation de chaque format.
- Recentrage du pilote et report des intégrations externes et de la conversion automatique en calques.
- Révision des hypothèses de coût, de délai, de crédits API, de modèles disponibles et de règles publicitaires.
- Conservation des propositions tarifaires comme hypothèses et remise en conformité de la progression avec les validations avant bootstrap et implémentation.
