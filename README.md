# atd

the Ability To Duplicate

## Motivation

Inspired by a discussion around data duplication during the "Meet the Partners" segment of Team Week 2025, this repository allows you to, with one command:

1. Copy all the geospatial assets from one blob storage to another using [obstore](https://developmentseed.org/obstore/)
2. Create a STAC item for each of those assets that includes a link back to original asset and a checksum so folks can verify that they're the same asset
3. Create a single [stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) to hold all of those items
