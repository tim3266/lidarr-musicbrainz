# lidarr-musicbrainz

Petit outil pour **préremplir l’éditeur de release MusicBrainz** quand Lidarr ne trouve pas la bonne édition (bonus tracks, expanded CD, etc.).

L’API publique MusicBrainz ne permet **pas** de créer une release complète en un POST XML : il faut passer par l’[éditeur web](https://musicbrainz.org/release/add). Ce dépôt génère les champs de [seeding](https://musicbrainz.org/doc/Development/Seeding/Release_Editor) à partir d’une release existante + pistes bonus.

## Installation

```bash
git clone https://github.com/tim3266/lidarr-musicbrainz.git
cd lidarr-musicbrainz
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage recommandé (sans mot de passe)

```bash
mb-seed-release -c examples/justin-bieber-journals-expanded.yaml --html mb-seed.html
```

1. Connecte-toi sur [musicbrainz.org](https://musicbrainz.org/login).
2. Ouvre `mb-seed.html` dans ton navigateur et envoie le formulaire.
3. Vérifie la tracklist (crée l’enregistrement **Alone** si besoin), ajoute une **edit note**, soumets.
4. Dans **Lidarr** : artiste → refresh metadata → album **Journals** → choisir la release **Expanded edition (17 tracks)** → search.

## Soumission automatique (optionnel)

Uniquement via variables d’environnement — **ne commite jamais** de mot de passe :

```bash
export MUSICBRAINZ_USER=ton_compte
export MUSICBRAINZ_PASSWORD=ton_mot_de_passe
mb-seed-release -c examples/justin-bieber-journals-expanded.yaml --submit --print-url
```

Tu devras quand même **valider** l’edit dans l’éditeur si MusicBrainz ne redirige pas directement.

## Fichier YAML

| Clé | Description |
|-----|-------------|
| `source_release_mbid` | Release MB à copier (tracklist + enregistrements 1–n) |
| `bonus_tracks` | Pistes en plus (`recording_mbid` si déjà connu) |
| `release_group_mbid` | Groupe d’album existant |
| `barcode`, `event_*`, `label_mbid` | Métadonnées de la nouvelle release |

Voir `examples/justin-bieber-journals-expanded.yaml`.

## Serveur à la demande (v0.2)

Le conteneur tourne en **mode serveur** : il ne regénère plus le HTML qu’au démarrage, mais quand tu le demandes.

| Méthode | URL | Rôle |
|---------|-----|------|
| GET | `/health` | Santé |
| GET | `/v1/album/{release-group-mbid}/status` | Releases MB (+ Lidarr si `LIDARR_API_KEY`) |
| GET | `/v1/album/{release-group-mbid}/suggest` | Analyse + action recommandée + YAML proposé si besoin |
| POST | `/v1/album/seed` | Génère `mb-seed.html` pour un YAML ou un JSON |

Exemples :

```bash
# Analyse Journals (MB vs Lidarr + que faire)
curl -s http://192.168.1.27:8787/v1/album/37b21c23-b70c-40c1-8c24-191ff84242c1/suggest

# État détaillé only
curl -s http://192.168.1.27:8787/v1/album/37b21c23-b70c-40c1-8c24-191ff84242c1/status

# Seed à la demande (YAML dans /config)
curl -s -X POST http://192.168.1.27:8787/v1/album/seed \
  -H 'Content-Type: application/json' \
  -d '{"config": "justin-bieber-journals-expanded.yaml"}'
```

Réponse : `html_url` à ouvrir dans le navigateur (connecté à MusicBrainz).

Variables : `LIDARR_MB_API_KEY` (protège POST), `LIDARR_URL`, `LIDARR_API_KEY`, `MB_RUN_MODE=once` pour l’ancien comportement au boot.

## Docker / OMV (`/appdata/mediarr`)

Comme **bazarr-translate** : clone sous `/appdata/mediarr/lidarr-musicbrainz`, mots de passe dans **`mediarr.env`**, service dans **`compose.override.yml`**.

Voir [deploy/omv/README.md](deploy/omv/README.md).

```bash
docker compose build lidarr-musicbrainz
docker compose up -d lidarr-musicbrainz
# http://<serveur>:8787/mb-seed.html
```

Variables utiles : `MUSICBRAINZ_USER`, `MUSICBRAINZ_PASSWORD`, `MB_SEED_CONFIG`, `MB_SEED_SUBMIT`, `MB_SEED_SERVE_PORT`.

## Lidarr

Les configs Lidarr (`/appdata/mediarr/lidarr/`) **ne contiennent pas** de compte MusicBrainz : Lidarr lit seulement l’API publique. Ce script sert à **enrichir** MusicBrainz pour que Lidarr voie la bonne release ensuite.

## Licence

MIT
