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
