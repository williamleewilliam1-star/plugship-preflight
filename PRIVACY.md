# Privacy Policy — PlugShip Preflight

Effective date: September 28, 2026

PlugShip Preflight includes a local developer tool and an optional browser-based Cloud Beta for reviewing public plugin repositories before directory submission.

## Data processed

PlugShip reads files inside the plugin directory selected by the user. Those files may contain source code, documentation, configuration, and incidental personal information such as author names or email addresses.

## Local scanner

The deterministic local scanner does not make network requests and does not transmit repository contents or scan results to BABYDOV. If the optional `--claude-validate` flag is used, PlugShip invokes the locally installed Claude Code validator; PlugShip itself does not add additional transmission.

## Cloud Beta

The Cloud Beta accepts public GitHub repository URLs. Selected repository metadata, plugin configuration, Skills, README, and license files are requested directly from GitHub by the user's browser. PlugShip does not proxy those repository contents through a BABYDOV application server.

Cloud Beta scan history is stored in the user's browser localStorage. Clearing browser site data removes that history. The current Cloud Beta does not provide server-side repository-history storage.

## Storage and retention

Local reports are written only to a local path selected by the user. The current Cloud Beta keeps recent scan summaries only in browser localStorage and does not maintain a PlugShip server-side repository database.

## Credentials

PlugShip is designed to detect likely accidentally committed credentials. It does not intentionally collect, store, or transmit credentials.

## Children

PlugShip is a developer tool and is not intended for users under 18.

## Contact

Questions can be opened through the public repository issue tracker:
https://github.com/williamleewilliam1-star/plugship-preflight/issues
