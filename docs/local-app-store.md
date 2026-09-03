# Local App Store

Place locally developed marketplace applications under `/opt/websoft9/data/local-apps`:

```text
local-apps/
  media/
    canvas.json
  library/
    apps/
      canvas/
        .env
        docker-compose.yml
        variables.json
        .env.external-db
        src/
```

Each `media/<key>.json` is one display record. Its file name is the application key and its optional `catalogBindings` uses the official catalog identifiers:

```json
{
  "title": "Canvas",
  "summary": "Local whiteboard",
  "catalogBindings": [{ "parentKey": "productivity", "childKey": "whiteboard" }]
}
```

The matching `library/apps/<key>/` directory uses the standard Library template format. `variables.json` must define at least one `edition`, and `.env`, `docker-compose.yml`, and `variables.json` are required.

In App Store, select **Local** and use the refresh action after changing the directory. Refresh creates `/opt/websoft9/data/local-apps/manifest/app-store-manifest.json`. Invalid applications are skipped with their error reported; if every candidate is invalid, the previous valid manifest remains active. Local installations use the standard AppHub installation pipeline, with their template sourced from the local Library directory.