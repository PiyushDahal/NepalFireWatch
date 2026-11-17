# Sentinel-2 context imagery

Nepal FireWatch can add optional true-colour Sentinel-2 L2A imagery around an event.

Source: Element 84 Earth Search STAC API
- Endpoint: `https://earth-search.aws.element84.com/v1`
- Collection: `sentinel-2-l2a`
- Asset: `visual` Cloud-Optimized GeoTIFF

The imagery is context only. It does not change fire confidence or lifecycle.

Defaults:
- 7 days before/after event
- max 60% scene cloud
- 8 km context width
- 720 x 720 JPEG
- retry every 12 h when unavailable
- max 3 imagery checks per pipeline run
