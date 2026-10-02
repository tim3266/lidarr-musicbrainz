# Configs album (monté sur OMV en `/config`)

Place ici tes YAML (un fichier par album / édition à seed).

Appel API :

```bash
curl -X POST http://omv:8787/v1/album/seed \
  -H 'Content-Type: application/json' \
  -H 'X-Api-Key: TA_CLE' \
  -d '{"config": "justin-bieber-journals-expanded.yaml"}'
```

Copie depuis `examples/` ou crée le tien.
