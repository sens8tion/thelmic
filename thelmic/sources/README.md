# thelmic.sources

Adapters for royalty-free / personal-use sample libraries. Search across
multiple sources, cache locally under `<repo>/.thelmic/samples/`, drop into
Live as Simpler/Sampler clips.

## Licensing matrix — read first

| Source             | License                                              | Personal use | Commercial release |
|--------------------|------------------------------------------------------|--------------|--------------------|
| `freesound`        | Per-sound: CC0, CC-BY, CC-Sampling+, etc.            | Yes          | **Per-sound** — check `Sound.license` and honour attribution |
| `bbc`              | BBC RemArc — personal / educational / research only  | Yes          | **No**             |
| `internet_archive` | Per-item: usually public domain or CC                | Yes          | **Per-item** — check `Sound.license` |
| `nasa`             | Public domain (NASA media usage guidelines)          | Yes          | Yes                |
| `fma`              | Disabled (API decommissioned 2018)                   | —            | —                  |
| `epidemic`         | Disabled (subscription-gated, not royalty-free)      | —            | —                  |

`Sound.license` is populated where the upstream API exposes it. Always treat
it as load-bearing — never assume "royalty-free" means "do anything".

## Setup

### 1. Credentials file

Per-source credentials live in `<repo>/.thelmic/.env` (gitignored). The loader
reads it once at `import thelmic.sources` time. Real environment variables
take precedence — set `FREESOUND_API_KEY` in your shell to override.

```
FREESOUND_API_KEY=...your token...
FREESOUND_CLIENT_ID=...your client id...
# FREESOUND_OAUTH_TOKEN=...   # optional — see "OAuth full-res" below
```

### 2. Get a Freesound API key (free)

1. Sign in at https://freesound.org
2. Go to https://freesound.org/apiv2/apply/
3. Fill the form — Name, URL (a project/repo URL is fine), Callback URL
   (`http://freesound.org/home/app_permissions/permission_granted/` for
   non-web apps), Description, accept the terms
4. Submit → the table at the top shows your **Client id** and **Api key**
5. Paste both into `.thelmic/.env`

Token auth gives you metadata + 30s preview MP3s (high quality, very usable
for sample chopping). For full-resolution originals, see OAuth below.

### 3. (Optional) Freesound OAuth for full-res downloads

The "Api key" doubles as the OAuth2 client secret; the "Client id" is the
client identifier. Standard Authorization Code flow:

```
1. Browser → https://freesound.org/apiv2/oauth2/authorize/?client_id=...&response_type=code
2. User clicks "Authorize"
3. Freesound redirects to your callback URL with ?code=...
4. POST https://freesound.org/apiv2/oauth2/access_token/
     grant_type=authorization_code & client_id=... & client_secret=... & code=...
5. Drop the returned access_token into FREESOUND_OAUTH_TOKEN in .thelmic/.env
```

Once set, `freesound.fetch()` uses the API download endpoint with bearer auth
and returns the original-quality file (WAV/FLAC/whatever the uploader posted).

### 4. No setup needed for

`bbc`, `internet_archive`, `nasa` — all unauthenticated public endpoints.

## Usage

### CLI

```
python -m thelmic.sources --list-sources
python -m thelmic.sources "amen break" --limit 5
python -m thelmic.sources "thunder" --source bbc --limit 3
python -m thelmic.sources "sub bass drone" --fetch          # download all hits
```

### Python

```python
from thelmic import sources

# Fan-out search (all enabled sources, interleaved by rank)
hits = sources.find("amen break", limit=10)
for h in hits:
    print(h.source, h.id, h.title, h.license)

# Single-source search
hits = sources.find("rain", limit=5, sources=["freesound"])

# Search with adapter-specific filters
from thelmic.sources import freesound
hits = freesound.search("kick drum", limit=10, max_duration=2, license="Creative Commons 0")

# Fetch into local cache
path = sources.fetch(hits[0])
print(path)  # <repo>/.thelmic/samples/freesound/<hash>.mp3
```

### Cache behaviour

- Default: `<repo>/.thelmic/samples/<source>/<hash>.<ext>`
- Override: set `THELMIC_CACHE=/some/abs/path`
- Re-`fetch()`-ing the same `Sound` is a no-op (idempotent on disk).

## Search recipes

| Goal                              | Recipe                                                        |
|-----------------------------------|---------------------------------------------------------------|
| One-shot drum hits                | `sources.find("kick", limit=20, sources=["freesound"])` then `freesound.search("snare", max_duration=1)` |
| Field recordings / ambience       | `sources.find("forest morning")` — BBC + IA + NASA all useful |
| Vocal stabs / chants              | `sources.find("vocal stab")` — mostly Freesound               |
| Granular fodder (long textures)   | `freesound.search("drone", max_duration=120)`                 |
| Strict CC0 only                   | `freesound.search(q, license="Creative Commons 0")`           |
| Spoken word / archival            | `internet_archive` is the right home                          |
| Spacecraft / cosmic ambience      | `sources.find("voyager", sources=["nasa"])`                   |

## Adapter contract

Each adapter module exposes:

```python
def available() -> bool: ...
def search(query: str, *, limit: int = 10, **filters) -> list[Sound]: ...
def fetch(sound: Sound) -> Path: ...
```

`Sound` (frozen dataclass): `source, id, title, url, download_url, duration,
license, tags, extra`.

To add a new source: drop `thelmic/sources/<name>.py` implementing the three
functions, then register it in `thelmic/sources/__init__.py::_ADAPTERS`.

## Known caveats

- **BBC** uses an undocumented Elasticsearch endpoint. If a redesign breaks
  it, the request body in `bbc.py` is the place to update.
- **Freesound** preview URLs require the `Authorization: Token ...` header on
  the CDN request — historically they were public. The adapter handles this.
- **Epidemic** is intentionally disabled. The free-credits download flow on
  the website is fine for personal listening, but the licensing terms tie
  use to an active subscription, and the API is paywalled.
