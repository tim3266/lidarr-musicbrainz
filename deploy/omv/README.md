# Déploiement OMV (`/appdata/mediarr`)

Même idée que **bazarr-translate** : dépôt git dans `mediarr`, secrets dans `mediarr.env`, service ajouté via **compose.override.yml**.

## 1. Cloner le dépôt

```bash
cd /appdata/mediarr
git clone https://github.com/tim3266/lidarr-musicbrainz.git
mkdir -p lidarr-musicbrainz/output
```

## 2. Variables dans `mediarr.env`

Ajoute (voir `.env.example`) :

```bash
MUSICBRAINZ_USER=ton_compte
MUSICBRAINZ_PASSWORD=ton_mot_de_passe
MB_SEED_CONFIG=/app/examples/justin-bieber-journals-expanded.yaml
MB_SEED_SUBMIT=false
MB_SEED_SERVE_PORT=8787
MB_SEED_PORT=8787
```

Ne commite **jamais** `mediarr.env`.

## 3. `compose.override.yml`

Copie le service `lidarr-musicbrainz` depuis `deploy/omv/docker-compose.yml` dans `/appdata/mediarr/compose.override.yml` (ou inclue-le).

Puis **toujours build avant up** (l’image n’existe pas sur Docker Hub) :

```bash
cd /appdata/mediarr
ls lidarr-musicbrainz/Dockerfile   # doit exister (git clone)
docker compose build lidarr-musicbrainz
docker compose up -d lidarr-musicbrainz
```

**Important :** les commandes `docker compose` se lancent depuis **`/appdata/mediarr`**, pas depuis `lidarr-musicbrainz/`.  
Sinon Compose cherche un `.env` dans le clone et n’utilise pas `mediarr.env` ni `compose.override.yml`.

### Erreur « pull access denied for lidarr-musicbrainz »

Compose a tenté de **télécharger** l’image au lieu de la **construire**. Causes fréquentes :

1. **`docker compose up` sans `build` avant** → lancer `docker compose build lidarr-musicbrainz` d’abord.
2. **Pas de clone** → `git clone …` dans `/appdata/mediarr/lidarr-musicbrainz`.
3. **Mauvais répertoire** → les commandes depuis `/appdata/mediarr` (là où sont `mediarr.yml` et `compose.override.yml`).

Le service utilise `pull_policy: never` pour éviter ce pull automatique.

## 4. Utilisation

- UI web : `http://<omv>:8787/app.html` (alias `/` et `/plugin-demo/app.html`).
- **Import bloqué en queue** : `LIDARR_API_KEY` + `LIDARR_URL` accessibles **depuis le conteneur** (souvent `http://lidarr:8686`, pas `127.0.0.1`). Monter le dossier de téléchargement en `:ro` et l’ajouter à `MB_ALLOWED_SCAN_PATHS`.
- Vérifier après **build** : `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/app.html` → **200** (ou `curl -sI …` une fois l’image à jour).
- Ouvre `http://<omv>:8787/mb-seed.html` (après génération au démarrage du conteneur).
- Connecte-toi sur MusicBrainz, envoie le formulaire, valide l’edit.
- Lidarr : refresh artiste → choisir la release 17 pistes.

Pour régénérer après changement de YAML :

```bash
docker compose restart lidarr-musicbrainz
```

Pour tenter le POST session (en plus du HTML) :

```bash
# dans mediarr.env
MB_SEED_SUBMIT=true
```

## YAML personnalisé

Monte un dossier :

```yaml
volumes:
  - ./lidarr-musicbrainz/config:/config:ro
```

et `MB_SEED_CONFIG=/config/mon-album.yaml`.
