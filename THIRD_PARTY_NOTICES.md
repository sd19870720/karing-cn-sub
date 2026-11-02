# Source and license notices

The proxy records in `subscription.yaml` are derived from
[Proxifly's free proxy list](https://github.com/proxifly/free-proxy-list),
which is distributed under the GNU General Public License version 3.
The upstream license text is reproduced without modification in `LICENSE`.

This repository's conversion script and generated configuration are distributed
under GPL-3.0-only. The complete conversion and validation source is included in
the `scripts/` directory.

Modifications made on 2026-11-02: combine four public candidate sources; select
country `CN`, protocols `http` (HTTP CONNECT) and `socks5`, public IP addresses and
valid ports; exclude authenticated entries; remove duplicate records by protocol,
address and port; translate known area labels; emit a Clash-compatible configuration
with stable node names and manual selection. Missing or unknown source city labels
are kept as candidates pending actual exit verification. HTTP and SOCKS5 records at
the same endpoint remain separate candidates. The updater performs bounded public
HTTPS and China-exit checks before publication, using at most 600 candidates,
16 concurrent workers and a five-minute probe budget. Published city labels come
from the actual exit checks. The check does not cover
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

Two further candidate sources are distributed under the MIT License:

- [databay-labs/free-proxy-list](https://github.com/databay-labs/free-proxy-list),
  Copyright (c) 2026 Databay Labs. Its unmodified license text is reproduced in
  `licenses/databay-MIT.txt`.
- [vakhov/fresh-proxy-list](https://github.com/vakhov/fresh-proxy-list),
  Copyright (c) 2023 Alex Vakhov. Its unmodified license text is reproduced in
  `licenses/vakhov-MIT.txt`.

Source inclusion or an upstream availability label does not bypass this
repository's independent HTTPS and mainland-China exit verification.
