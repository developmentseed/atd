# atd

the Ability To Duplicate

> [!WARNING]
> This is a proof-of-concept that is not intended for production use.

![A gif of the thing working](./img/atd.gif)

## Motivation

Inspired by a discussion around data duplication during the "Meet the Partners" segment of Team Week 2025, this repository allows you to, with one command:

1. Copy all the geospatial assets from one blob storage to another using [obstore](https://developmentseed.org/obstore/)
2. Create a STAC item for each of those assets that includes a link back to original asset and a checksum so folks can verify that they're the same asset
3. Create a single [stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) to hold all of those items

## Usage

Install:

```shell
python -m pip install git+ssh://git@github.com/developmentseed/atd.git
```

Then:

```shell
$ atd s3://maxar-opendata/events/Marshall-Fire-21-Update/13/031131113030/2021-12-30 ~/Desktop
Getting 10200100BCB1A500-pan.tif (44.62 MB)
Getting 10200100BCB1A500-visual.tif (18.02 MB)
Got 10200100BCB1A500-visual.tif (18.02 MB in 2.56s)
Creating STAC item for 10200100BCB1A500-visual.tif
Created STAC item for 10200100BCB1A500-visual.tif (0.07s)
Putting 10200100BCB1A500-visual.tif (18.02 MB)
Put 10200100BCB1A500-visual.tif (18.02 MB in 0.02s)
Got 10200100BCB1A500-pan.tif (44.62 MB in 5.24s)
Creating STAC item for 10200100BCB1A500-pan.tif
Created STAC item for 10200100BCB1A500-pan.tif (0.03s)
Putting 10200100BCB1A500-pan.tif (44.62 MB)
Put 10200100BCB1A500-pan.tif (44.62 MB in 0.01s)
Putting items.geoparquet
Items are available at file:///Users/gadomski/Desktop/items.geoparquet
```

There's two assets:

```shell
$ stacrs translate ~/Desktop/items.geoparquet | jq '.features.[] | .assets' 
{
  "original": {
    "href": "s3://maxar-opendata/events/Marshall-Fire-21-Update/13/031131113030/2021-12-30/10200100BCB1A500-pan.tif",
    "file:checksum": "12202f1ea332dd0e7a559b78e16952c5b9be81e44ddf9768634db12dcb311b3f587f"
  },
  "data": {
    "href": "file:///Users/gadomski/Desktop/10200100BCB1A500-pan.tif",
    "type": "image/tiff; application=geotiff",
    "roles": [
      "data"
    ],
    "file:checksum": "12202f1ea332dd0e7a559b78e16952c5b9be81e44ddf9768634db12dcb311b3f587f"
  }
}
{
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
```

You can use `stacrs serve` to browse them:

```shell
stacrs serve ~/Desktop/items.parquet
```

Then go to <https://radiantearth.github.io/stac-browser/#/external/http:/127.0.0.1:7822> to browse.

## Limitations

- Right now you can't write to AWS: <https://github.com/stac-utils/stac-rs/issues/414>
- There's no guards on the number of simultaneous downloads, so you could swamp yourself pretty easily
- No configuration (yet)
