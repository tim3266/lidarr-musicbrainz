# Démo visuelle plugin Lidarr (sans code .NET)

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
