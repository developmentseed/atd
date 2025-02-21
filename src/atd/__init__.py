import asyncio
import datetime
import urllib.parse
from pathlib import Path

import click
import obstore
import obstore.store
import rio_stac
import stacrs
import tqdm
import tqdm.asyncio
from multiformats import multihash
from pystac import Asset
from rasterio import MemoryFile


@click.command
@click.argument("source")
@click.argument("destination")
def cli(source: str, destination: str) -> None:
    timeout = datetime.timedelta(minutes=10)
    source = to_url(source)
    source_store = obstore.store.from_url(source, timeout=timeout)
    destination = to_url(destination)
    destination_store = obstore.store.from_url(destination)
    items = []
    chunk_size = 5 * 1024 * 1024

    async def run() -> None:
        pages = list(obstore.list(source_store))
        nfiles = 0
        for page in tqdm.tqdm(pages, desc="pages", position=0):
            for entry in tqdm.tqdm(page, desc="page", position=1):
                path: str = entry["path"]
                if "." not in path:
                    continue
                id, ext = path.rsplit(".")
                if ext not in ("tif", "tiff"):
                    continue
                size = entry["size"]

                response = await obstore.get_async(source_store, path)
                data = b""
                progress = tqdm.tqdm(
                    total=size,
                    unit="B",
                    unit_scale=True,
                    desc=path,
                    position=nfiles + 2,
                    leave=False,
                )
                nfiles += 1
                async for chunk in response.stream(min_chunk_size=chunk_size):
                    progress.update(len(chunk))
                    data += bytes(chunk)
                destination_href = destination.rstrip("/") + "/" + path
                with MemoryFile(data) as memory_file:
                    with memory_file.open() as dataset:
                        item = rio_stac.create_stac_item(
                            dataset,
                            asset_href=destination_href,
                            asset_roles=["data"],
                            id=id,
                            with_eo=True,
                            with_proj=True,
                            with_raster=True,
                        )
                checksum = multihash.digest(data, "sha2-256").hex()
                item.ext.add("file")
                asset = item.assets["asset"]
                asset.ext.file.checksum = checksum
                original = Asset(href=source.rstrip("/") + "/" + path)
                original.ext.file.checksum = checksum
                item.assets = {"data": asset, "original": original}
                items.append(
                    item.to_dict(include_self_link=False, transform_hrefs=False)
                )
                await obstore.put_async(destination_store, entry["path"], data)

        await stacrs.write(destination.rstrip("/") + "/" + "items.geoparquet", items)

    asyncio.run(run())


def to_url(s: str) -> str:
    if urllib.parse.urlparse(s).scheme:
        return s
    else:
        return "file://" + str(Path(s).absolute())


if __name__ == "__main__":
    cli()
