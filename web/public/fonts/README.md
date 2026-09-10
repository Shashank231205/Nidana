# Fonts

Archivo and Newsreader, vendored rather than fetched.

Nidana runs on-premise with no network egress, so a webfont CDN would be a
runtime dependency the product cannot have: a clinic with no internet would
lose its typography, and the request itself would leak that the clinic is
running Nidana.

Both faces are licensed under the SIL Open Font License 1.1, which permits
redistribution alongside the software. Both are variable, latin subset.

| File | Family | Axis | Source |
|---|---|---|---|
| `Archivo-Variable.woff2` | Archivo | weight 400-700 | Google Fonts v25 |
| `Newsreader-Italic-Variable.woff2` | Newsreader Italic | weight 400-600 | Google Fonts v26 |

Archivo is the interface face. Newsreader Italic is used for exactly one
thing: the patient's own words quoted verbatim on the clinician screen. The
switch to serif italic marks it as a different voice from the system's.

To refresh, resolve the `woff2` URL from the Google Fonts CSS API and download
it directly. Do not add a `<link>` to the CDN.
