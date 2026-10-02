# Démo visuelle plugin Lidarr (sans code .NET)

## Lien dans Lidarr (userscript)

Comme la maquette, mais dans **ton** Lidarr :

1. Installe **Tampermonkey** (ou Violentmonkey) dans le navigateur où tu ouvres Lidarr.
2. Crée un script à partir de [`lidarr-musicbrainz.user.js`](lidarr-musicbrainz.user.js).
3. Adapte en tête de fichier :
   - `@match` → l’URL de ton Lidarr (port **8686**)
   - `MB_APP_URL` → ton service, ex. `http://192.168.1.27:8787/app.html`
4. Recharge Lidarr : sous **System**, une ligne **MusicBrainz Helper** apparaît ; un clic ouvre l’app dans **une nouvelle fenêtre**.

Sur une **fiche album** (`/album/{release-group-mbid}`), un **bandeau** affiche le **release group** et la **release** (édition surveillée) en entier, avec boutons **Copier**. Lidarr natif met ses liens dans le tooltip **Links**.

Vérifie que Tampermonkey est actif sur **exactement** l’URL du navigateur. **`LIDARR_API_KEY`** dans le script (Settings → General) est nécessaire pour remplir la release ; le release group vient toujours de l’URL.

Sur **System → Plugins**, un encart rappelle le même bouton (comme la démo « plugin installé »).

Page servie par Docker : `http://<host>:8787/app.html` (analyse MBID, bouton **Créer une release**).

---

## Voir la maquette

Ouvre dans un navigateur :

```bash
xdg-open plugin-demo/preview.html
```

Ou depuis le conteneur (après rebuild) : copier le fichier et l’ouvrir en local.

Tu peux naviguer dans la barre latérale :

- **System → Plugins** — liste des plugins installés
- **Settings** — onglet fictif **MusicBrainz Helper**
- **Albums** — fiche **Journals** avec boutons grisés (objectif futur)

Aucune requête réseau : **pure maquette**.

## Plugin Lidarr réel

Un plugin installable demande :

- branche Lidarr **develop / nightly / pr-plugins**
- projet **.NET 8** + sources Lidarr en submodule
- CI GitHub qui publie un **.zip** installé via **System → Plugins**

Le squelette minimal côté code ne fait qu’enregistrer `Name` / `Owner` / `GithubUrl` ; l’UI Settings vient des **providers** (indexer, metadata, etc.), pas d’un bouton libre sur la fiche album.

Pour la logique MusicBrainz, le **serveur Docker 8787** reste la solution la plus simple ; un plugin serait surtout un raccourci vers ce service.
