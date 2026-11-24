# NuvioTorrent

Implémentation expérimentale du ticket [NuvioTV #4002](https://github.com/NuvioMedia/NuvioTV/issues/4002), pour Android TV et Android mobile, avec adaptation de TR4KERIO.

Le dépôt contient des correctifs appliqués à des versions précises des applications officielles, un addon TR4KERIO prêt à être testé et un workflow GitHub Actions. Les applications complètes sont récupérées pendant la compilation : inutile de dupliquer leurs bibliothèques et leurs historiques dans ce dépôt.

## État de validation

- Les tests JavaScript de TR4KERIO et des deux contrats de résolution ont été exécutés localement.
- Les correctifs sont vérifiés sur les commits de `upstreams.json`.
- La compilation Android et les tests Kotlin doivent passer dans GitHub Actions avant installation.
- Un test JNI sur émulateur est disponible ; une lecture réelle avec C411 reste à vérifier sur appareil.
- Aucune PR n'est soumise aux projets officiels. Leur processus d'approbation des nouvelles fonctionnalités reste distinct de ce prototype.

## Compiler avec GitHub Actions

Publier le contenu de ce dossier à la racine de `NuvioTorrent`. Le workflow **NuvioTorrent Android** se déclenche lors d'un push sur `main`, d'une PR ou manuellement dans **Actions → Run workflow**.

Il exécute les tests puis produit deux artefacts :

- `NuvioTorrent-tv-debug`, contenant les APK Android TV ;
- `NuvioTorrent-mobile-debug`, contenant l'APK Android téléphone/tablette.

Cocher **native_smoke** lors d'un lancement manuel pour vérifier aussi l'import d'un torrent privé synthétique par la véritable bibliothèque Android JNI. Le runner utilise `sudo` uniquement pour donner à l'émulateur accès au périphérique KVM du runner GitHub.

Les secrets facultatifs `NUVIO_TV_LOCAL_PROPERTIES_BASE64` et `NUVIO_MOBILE_LOCAL_PROPERTIES_BASE64` fournissent les configurations d'exécution propres aux applications, notamment `TMDB_API_KEY`. Une compilation sans configuration ne fournit pas les clés privées des applications officielles. Ne pas placer de clé C411 dans ces fichiers : elle appartient à la configuration de TR4KERIO.

Ces builds utilisent des signatures de développement. La signature TV générée peut changer entre exécutions ; ne pas compter sur une mise à jour transparente d'une installation existante signée autrement. Les APK ne constituent pas des versions officielles Nuvio.

## Tester avec TR4KERIO

Utiliser la copie `tr4kerio/` de ce dépôt. Le dossier d'origine de l'utilisateur n'est pas modifié.

```bash
cd tr4kerio
npm install
npm test
npm start
```

Dans la page de configuration, sélectionner **NuvioTorrent — moteur natif (.torrent)**. Le manifeste devient :

```text
https://DOMAINE/CLE_API/1080p/native/manifest.json
```

Installer ce manifeste dans le build modifié et activer la lecture P2P. La recherche retourne une URL de métadonnées ; seul le `.torrent` sélectionné est téléchargé par l'appareil Android. Pour les séries, l'application recherche l'épisode dans la liste de fichiers fournie par le moteur, en conservant les index originaux.

Le mode `/https/` historique reste disponible pour Stremio et Nuvio standard. Le mode `/native/` conserve les annonces intégrées au fichier : le relais `TRACKER_PROXY_URL` du mode historique ne réécrit pas ces annonces. L'appareil doit pouvoir joindre le tracker original.

## Contrat HTTP et JavaScript

Un stream peut fournir un objet `torrent` avec **exactement un** des champs `url`, `dataBase64`, ou, pour les plugins JS uniquement, `resolveId`.

```json
{
  "name": "Example",
  "torrent": {
    "url": "https://provider.example/download/42",
    "headers": {"Authorization": "Bearer EXEMPLE"},
    "season": 1,
    "episode": 2
  }
}
```

Les sélecteurs facultatifs sont `fileIdx` (index natif commençant à zéro), `filename` (chemin ou nom exact), ou le couple `season`/`episode`. Un index explicite prime. Un épisode absent ou un index invalide provoque une erreur ; aucun autre épisode n'est lancé par défaut. Pour un film sans sélecteur, le plus grand fichier vidéo hors sample est retenu.

Résolution JavaScript différée :

```javascript
module.exports.getStreams = async function (tmdbId, mediaType, season, episode) {
  return [{ title: 'Example', torrent: { resolveId: 'source-42', season, episode } }];
};

module.exports.resolveTorrent = async function (id) {
  // Authentification et rafraîchissement de session à réaliser dans le plugin.
  const response = await fetch(authenticatedDownloadUrlFor(id));
  if (!response.ok) throw new Error('Authentication or download failed');
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return { dataBase64: btoa(binary) };
};
```

`resolveTorrent` reçoit la chaîne `resolveId` et renvoie directement l'objet de métadonnées, sans enveloppe `streams` ou `torrent`. Il s'exécute dans une nouvelle instance du runtime, avec le code et les réglages du plugin utilisés lors de la recherche ; les variables JS de cette recherche ne sont pas conservées. Le résolveur doit donc retrouver sa source à partir de son identifiant. Un changement de réglages nécessite de relancer la recherche.

La limite native de **4 Mio** porte sur les octets décodés. La limite Base64 est vérifiée avant décodage ; les téléchargements trop grands et les réponses binaires tronquées sont rejetés. Une URL de métadonnées peut être renouvelée par `resolveTorrent` au moment du clic. Les redirections du téléchargement hôte ne transmettent pas les en-têtes personnalisés à une autre origine et refusent une rétrogradation HTTPS vers HTTP.

## Traitement des données authentifiées

Les descripteurs et les callbacks sont conservés dans un registre mémoire borné. La navigation ne reçoit qu'une référence opaque. Ces sources sont exclues du cache de liens réutilisables ; après redémarrage de l'application, il faut relancer la recherche. Les erreurs du téléchargement et du moteur sont expurgées, et la console JS est masquée pendant `resolveTorrent`.

L'application appelle `addTorrent(ByteArray)` sans reconstruire de magnet ni ajouter de trackers publics. Chaque sélection crée un état moteur isolé dans le cache Android, pour éviter la fusion avec des annonces ou des passkeys anciennes. Le téléchargement des morceaux utilise le cache de contenu existant. Le moteur peut enregistrer ses métadonnées de reprise dans cet état local : il ne s'agit donc pas d'une garantie d'absence de données sensibles sur disque. Cet état ne fait pas partie de la synchronisation des profils.

Les restrictions DHT/PEX/LSD des torrents portant `private=1` restent appliquées par libtorrent, intégré au moteur. Le test JNI vérifie la conservation du hash incluant ce drapeau et des index de fichiers ; il ne capture pas le trafic DHT/PEX/LSD. Leur absence pour le torrent privé et une lecture réelle restent à contrôler avant de déclarer la compatibilité complète.

## Préparer et maintenir les sources

```bash
python3 scripts/prepare.py tv
python3 scripts/prepare.py mobile
```

Ces commandes récupèrent les sources dans `work/` puis appliquent les patches. Elles refusent un mauvais commit ou un patch déjà appliqué et n'effectuent ni reset ni suppression.

Dans le workspace de développement fourni, les arbres modifiés `../NuvioTV` et `../NuvioMobile` sont disponibles pour revue. Après une modification :

```bash
python3 scripts/export-patches.py
```

Lors d'une mise à jour des versions officielles, revoir les correctifs avant de changer `upstreams.json` et les commits du workflow. Les licences des projets officiels continuent de s'appliquer aux applications et au code modifié.
