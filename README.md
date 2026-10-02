# lidarr-musicbrainz

Outil pour **Lidarr** quand la bonne **édition** d’un album manque dans les métadonnées (expanded CD, bonus tracks, etc.).

1. **Enrichir MusicBrainz** via l’[éditeur web](https://musicbrainz.org/release/add) (seeding).
2. **Comparer** MusicBrainz au cache **Servarr** (via l’API Lidarr).
3. **Générer à la demande** le formulaire HTML pour soumettre une release.

L’API MusicBrainz ne permet **pas** de créer une release complète en un seul POST : il faut passer par l’éditeur. Ce dépôt prépare les champs documentés [ici](https://musicbrainz.org/doc/Development/Seeding/Release_Editor).

## Chaîne metadata (important)

```text
MusicBrainz  →  serveur metadata Servarr  →  Lidarr (ta base)
     ↑                    ↑                        ↑
  edits ici          délai / cache            Refresh artiste
```

Créer ou corriger une release sur MusicBrainz **ne met pas à jour Lidarr tout de suite**. Il faut attendre Servarr (souvent des heures) puis **Refresh** dans Lidarr. Voir [Metadata Troubleshooting Servarr](https://wiki.servarr.com/lidarr/metadata-troubleshooting).

---

## Déploiement OMV (recommandé)

Comme **bazarr-translate** : dépôt dans `/appdata/mediarr`, secrets dans **`mediarr.env`**, service dans **`compose.override.yml`** (ne pas éditer `mediarr.yml`, regénéré par OMV).

Guide détaillé : [deploy/omv/README.md](deploy/omv/README.md).

```bash
cd /appdata/mediarr
git clone https://github.com/tim3266/lidarr-musicbrainz.git
mkdir -p lidarr-musicbrainz/output lidarr-musicbrainz/config
# Copier le service lidarr-musicbrainz depuis deploy/omv/docker-compose.yml → compose.override.yml
docker compose build lidarr-musicbrainz
docker compose up -d lidarr-musicbrainz
```

**Les commandes `docker compose` se lancent depuis `/appdata/mediarr`**, pas depuis le sous-dossier `lidarr-musicbrainz/`.

L’image n’est **pas** sur Docker Hub : toujours `docker compose build` avant `up`.

---

## Variables d’environnement (`mediarr.env`)

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `MUSICBRAINZ_USER` | Non | Compte MusicBrainz (uniquement si submit auto) |
| `MUSICBRAINZ_PASSWORD` | Non | Mot de passe MB — **ne jamais commiter** |
| `MUSICBRAINZ_APP_CONTACT` | Recommandé | Contact User-Agent MB (`mailto:…` ou URL GitHub) |
| `LIDARR_URL` | Non | URL Lidarr, ex. `http://127.0.0.1:8686` |
| `LIDARR_API_KEY` | Non | Clé Lidarr (Settings → General) — pour `/status` et `/suggest` |
| `LIDARR_MB_API_KEY` | Recommandé | **Clé que tu inventes** pour protéger **cet outil** (header `X-Api-Key`). Ce n’est **pas** la clé Lidarr. |
| `MB_SEED_SERVE_PORT` | Non | Port HTTP (défaut `8787`) |
| `MB_RUN_MODE` | Non | `server` (défaut) ou `once` (génère le HTML au boot puis quitte) |
| `MB_SEED_SUBMIT` | Non | `true` = tente aussi un POST session MB (en plus du HTML) |

Modèle : [deploy/omv/.env.example](deploy/omv/.env.example).

Si `LIDARR_MB_API_KEY` est définie, les routes API ci-dessous exigent :

```http
X-Api-Key: < même valeur >
```

Si elle est **vide**, le serveur accepte les requêtes sans clé (pratique en test, éviter sur un LAN ouvert).

---

## API HTTP (mode serveur)

Port par défaut : **8787**.

| Méthode | Chemin | Rôle |
|---------|--------|------|
| GET | `/health` | Santé |
| GET | `/v1/album/{release-group-mbid}/status` | Liste des releases MB + comparaison Lidarr |
| GET | `/v1/album/{release-group-mbid}/suggest` | Analyse : que faire ? YAML proposé si seed MB utile |
| POST | `/v1/album/seed` | Génère `mb-seed.html` |
| GET | `/mb-seed.html` | Dernière génération |
| GET | `/output/{job_id}/mb-seed.html` | Génération d’un job précis |
| GET | `/app.html` | UI web (analyse release group, lien seed) — cible du userscript Lidarr |
| GET | `/plugin-demo/preview.html` | Maquette UI plugin Lidarr (démo visuelle) |

### Lien dans l’UI Lidarr

Lidarr ne permet pas d’ajouter un menu natif sans plugin .NET. Le dépôt fournit un **userscript** ([`plugin-demo/lidarr-musicbrainz.user.js`](plugin-demo/lidarr-musicbrainz.user.js)) : entrée **System → MusicBrainz Helper** qui ouvre `http://<host>:8787/app.html` dans une nouvelle fenêtre. Voir [plugin-demo/README.md](plugin-demo/README.md).

**Release group** = ce que Lidarr appelle l’« album » (MBID du groupe, pas d’une pression CD).

### Exemple : Justin Bieber – Journals

Release group : `37b21c23-b70c-40c1-8c24-191ff84242c1`

```bash
API=http://192.168.1.27:8787
KEY=ta_lidarr_mb_api_key   # si définie dans mediarr.env
HDR=(-H "X-Api-Key: $KEY") # omit if no key

# 1) Analyse (MB vs Servarr/Lidarr)
curl -s "${HDR[@]}" "$API/v1/album/37b21c23-b70c-40c1-8c24-191ff84242c1/suggest" | jq .

# 2) Générer le seed (YAML dans config/ monté en /config)
curl -s -X POST "${HDR[@]}" "$API/v1/album/seed" \
  -H 'Content-Type: application/json' \
  -d '{"config": "justin-bieber-journals-expanded.yaml"}' | jq .

# 3) Ouvrir html_url dans le navigateur (connecté à MusicBrainz), valider l’edit
```

Seed depuis la suggestion auto (si `proposed_seed_yaml` non null) :

```bash
curl -s -X POST "${HDR[@]}" "$API/v1/album/seed" \
  -H 'Content-Type: application/json' \
  -d '{"from_suggest": true, "release_group_mbid": "37b21c23-b70c-40c1-8c24-191ff84242c1"}'
```

Réponses `recommended_action` typiques :

| Valeur | Signification |
|--------|----------------|
| `refresh_lidarr` | MusicBrainz OK, Servarr/Lidarr en retard → attendre ou refresh artiste |
| `seed_musicbrainz` | Édition à créer sur MB → utiliser `proposed_seed_yaml` + `/seed` |
| `fix_musicbrainz` | Tracklists incomplètes sur MB |

---

## Workflow manuel (après seed HTML)

1. Connexion [musicbrainz.org](https://musicbrainz.org/login).
2. Ouvrir le HTML généré et envoyer le formulaire vers l’éditeur.
3. Vérifier tracklist, **edit note**, soumettre l’edit.
4. **Lidarr** : Refresh artiste → album → choisir la release (ex. **Expanded edition**, 17 pistes) → Search ou import manuel.

### Autre album que Journals

Justin Bieber n’est **qu’un exemple** (`examples/` et copie dans `config/`). Rien n’est publié automatiquement en mode **`server`** (défaut).

1. Trouve le **release group** MBID sur [MusicBrainz](https://musicbrainz.org) (type *Release group*, pas une release CD).
2. `GET /v1/album/{mbid}/suggest` → voir si tu dois **seed** MB ou seulement **refresh Lidarr**.
3. Crée un YAML dans `config/` à partir de [config/album-template.yaml](config/album-template.yaml).
4. `POST /v1/album/seed` avec `{"config": "ton-fichier.yaml"}`.

Lister les YAML disponibles : `GET /v1/configs`.

**Éviter** `MB_RUN_MODE=once` + `MB_SEED_SUBMIT=true` avec le YAML Justin au boot : ça ne relancerait que cet exemple. En **`server`**, tu choisis l’album à chaque `POST /seed`.

Exemple : [examples/justin-bieber-journals-expanded.yaml](examples/justin-bieber-journals-expanded.yaml).

---

## Installation locale (dev)

```bash
git clone https://github.com/tim3266/lidarr-musicbrainz.git
cd lidarr-musicbrainz
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# One-shot
mb-seed-release -c examples/justin-bieber-journals-expanded.yaml --html mb-seed.html

# Serveur
mb-seed-release serve
# ou : mb-album-server
```

User-Agent : MusicBrainz refuse certains noms (`lidarr-musicbrainz` en minuscules → 403). L’outil utilise `LidarrMusicBrainz`.

---

## Fichier YAML (seed)

| Clé | Description |
|-----|-------------|
| `release_group_mbid` | Album MusicBrainz (release group) |
| `source_release_mbid` | Release existante à copier (pistes 1–n) |
| `bonus_tracks` | Pistes supplémentaires (`recording_mbid` si connu) |
| `artist_mbid`, `name`, `disambiguation` | Crédits et titre |
| `barcode`, `event_*`, `label_mbid`, `catalog_number` | Release event / label |

---

## Commandes CLI

| Commande | Rôle |
|----------|------|
| `mb-seed-release -c fichier.yaml --html out.html` | Génération locale one-shot |
| `mb-seed-release serve` | Démarre le serveur HTTP |
| `mb-album-server` | Idem serveur |

---

## Licence

MIT
