# Privacy Policy — PlugShip Preflight

Effective date: September 28, 2026

PlugShip Preflight is a local developer tool for reviewing Claude plugin repositories before directory submission.

## Data processed

PlugShip reads files inside the plugin directory selected by the user. Those files may contain source code, documentation, configuration, and incidental personal information such as author names or email addresses.

## Data transmission

The deterministic scanner does not make network requests and does not transmit repository contents or scan results to BABYDOV or any third-party service.

If the optional `--claude-validate` flag is used, PlugShip invokes the locally installed Claude Code validator. PlugShip itself does not add any additional network transmission.

## Storage and retention

PlugShip does not maintain a server-side database and does not retain user repository contents. Reports are written only to the local path selected by the user.

## Credentials

PlugShip is designed to detect likely accidentally committed credentials. It does not intentionally collect, store, or transmit credentials.

## Children

PlugShip is a developer tool and is not intended for users under 18.

## Contact

Questions can be opened through the public repository issue tracker:
https://github.com/williamleewilliam1-star/plugship-preflight/issues
