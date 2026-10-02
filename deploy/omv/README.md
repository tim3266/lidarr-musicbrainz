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

Puis :

```bash
cd /appdata/mediarr
docker compose build lidarr-musicbrainz
docker compose up -d lidarr-musicbrainz
```

## 4. Utilisation

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
