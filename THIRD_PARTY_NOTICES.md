# Source and license notices

The proxy records in `subscription.yaml` are derived from
[Proxifly's free proxy list](https://github.com/proxifly/free-proxy-list),
which is distributed under the GNU General Public License version 3.
The upstream license text is reproduced without modification in `LICENSE`.

This repository's conversion script and generated configuration are distributed
under GPL-3.0-only. The complete conversion source is included in `scripts/update.py`.

Modifications made on 2026-11-02: select country `CN`, protocol `socks5`,
nonempty known area labels, public IP addresses and valid ports; remove duplicate
endpoints; translate known area labels; emit a Clash-compatible configuration
with stable node names and manual selection. The updater now performs bounded
public HTTPS and China-exit checks before publication. The check does not cover
iPhone connectivity or any authenticated application. Upstream metadata is not a guarantee of location,
availability, anonymity, or compatibility with any particular application.
