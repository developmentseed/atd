import asyncio
import datetime
import time
import urllib.parse
from asyncio import Queue, TaskGroup
from pathlib import Path
from typing import Any

import click
import obstore
import obstore.store
import rio_stac
import stacrs
from multiformats import multihash
from pystac import Asset, Item
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
    messages = Queue()

    async def run() -> None:
        pages = list(obstore.list(source_store))
        tasks = []
        asyncio.create_task(print_messages(messages))
        async with TaskGroup() as task_group:
            for page in pages:
                for entry in page:
                    path: str = entry["path"]
                    if "." not in path:
                        continue
                    id, ext = path.rsplit(".", 1)
                    if ext not in ("tif", "tiff"):
                        continue

                    tasks.append(
                        task_group.create_task(
                            duplicate(
                                source,
                                source_store,
                                destination,
                                destination_store,
                                path,
                                id,
                                entry["size"],
                                messages,
                            )
                        )
                    )

        items = [task.result().to_dict() for task in tasks]
        await messages.put("Putting items.geoparquet")
        geoparquet_path = destination.rstrip("/") + "/" + "items.geoparquet"
        await stacrs.write(geoparquet_path, items)
        await messages.put("Put items.geoparquet")
        await messages.put(None)
        print(f"Items are available at {geoparquet_path}")

    asyncio.run(run())


def to_url(s: str) -> str:
    if urllib.parse.urlparse(s).scheme:
        return s
    else:
        return "file://" + str(Path(s).absolute())


async def duplicate(
    source: str,
    source_store: Any,  # https://github.com/developmentseed/obstore/issues/186
    destination: str,
    destination_store: Any,  # https://github.com/developmentseed/obstore/issues/186
    path: str,
    id: str,
    size: int,
    messages: Queue,
) -> Item:
    response = await obstore.get_async(source_store, path)
    data = b""
    await messages.put(f"Getting {path} ({size / 1_000_000:.2f} MB)")
    start = time.time()
    data += bytes(await response.bytes_async())
    await messages.put(
        f"Got {path} ({size / 1_000_000:.2f} MB in {time.time() - start:.2f}s)"
    )
    destination_href = destination.rstrip("/") + "/" + path

    await messages.put(f"Creating STAC item for {path}")
    start = time.time()
    with MemoryFile(data) as memory_file:
        with memory_file.open() as dataset:
            item = rio_stac.create_stac_item(
                dataset,
                asset_href=destination_href,
                asset_roles=["data"],
                id=id,
                with_eo=False,
                with_proj=False,
                with_raster=False,
            )
    checksum = multihash.digest(data, "sha2-256").hex()
    item.ext.add("file")
    asset = item.assets["asset"]
    asset.ext.file.checksum = checksum
    original = Asset(href=source.rstrip("/") + "/" + path)
    original.ext.file.checksum = checksum
    item.assets = {"data": asset, "original": original}
    await messages.put(f"Created STAC item for {path} ({time.time() - start:.2f}s)")

    await messages.put(f"Putting {path} ({size / 1_000_000:.2f} MB)")
    start = time.time()
    await obstore.put_async(destination_store, path, data)
    await messages.put(
        f"Put {path} ({size / 1_000_000:.2f} MB in {time.time() - start:.2f}s)"
    )

    return item


async def print_messages(queue: Queue) -> None:
    while True:
        message = await queue.get()
        if message is None:
            queue.task_done()
            break
        else:
            print(message)
            queue.task_done()


if __name__ == "__main__":
    cli()
