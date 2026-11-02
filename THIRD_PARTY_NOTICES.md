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

An additional candidate source is [monosans/proxy-list](https://github.com/monosans/proxy-list),
Copyright (c) 2022 monosans, under the MIT License reproduced in
`licenses/monosans-MIT.txt`. Entries containing authentication credentials are excluded.
That source uses GeoLite data created by MaxMind (https://www.maxmind.com),
with geolocation/ASN metadata subject to CC BY-SA 4.0 and the GeoLite EULA as
described in its README. This updater uses the upstream country classification
for candidate selection; it does not republish the upstream ASN records.
Published area labels are independently obtained from the HTTPS exit check.
