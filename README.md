# atd

the Ability To Duplicate

## Usage

```shell
$ python -m pip install git+ssh://git@github.com/developmentseed/atd.git
$ atd s3://maxar-opendata/events/Marshall-Fire-21-Update/13/031131113030/2021-12-30 ~/Desktop
page: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 4/4 [03:40<00:00, 55.10s/it]
pages: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1/1 [03:40<00:00, 220.41s/it]

$ stacrs translate ~/Desktop/items.geoparquet | jq '.features.[] | { id: .id, assets: .assets }'
{
  "id": "10200100BCB1A500-pan",
  "assets": {
    "data": {
      "href": "file:///Users/gadomski/Desktop/10200100BCB1A500-pan.tif",
      "type": "image/tiff; application=geotiff",
      "roles": [
        "data"
      ],
      "file:checksum": "12202f1ea332dd0e7a559b78e16952c5b9be81e44ddf9768634db12dcb311b3f587f"
    },
    "original": {
      "href": "s3://maxar-opendata/events/Marshall-Fire-21-Update/13/031131113030/2021-12-30/10200100BCB1A500-pan.tif",
      "file:checksum": "12202f1ea332dd0e7a559b78e16952c5b9be81e44ddf9768634db12dcb311b3f587f"
    }
  }
}
{
  "id": "10200100BCB1A500-visual",
  "assets": {
    "original": {
      "href": "s3://maxar-opendata/events/Marshall-Fire-21-Update/13/031131113030/2021-12-30/10200100BCB1A500-visual.tif",
      "file:checksum": "122068b0865a5ed7d91c4d19bd9756325499a77e5f4403ab1c36e4476fa697fb0cd7"
    },
    "data": {
      "href": "file:///Users/gadomski/Desktop/10200100BCB1A500-visual.tif",
      "type": "image/tiff; application=geotiff",
      "roles": [
        "data"
      ],
      "file:checksum": "122068b0865a5ed7d91c4d19bd9756325499a77e5f4403ab1c36e4476fa697fb0cd7"
    }
  }
}
```

## Motivation

Inspired by a discussion around data duplication during the "Meet the Partners" segment of Team Week 2025, this repository allows you to, with one command:

1. Copy all the geospatial assets from one blob storage to another using [obstore](https://developmentseed.org/obstore/)
2. Create a STAC item for each of those assets that includes a link back to original asset and a checksum so folks can verify that they're the same asset
3. Create a single [stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) to hold all of those items
