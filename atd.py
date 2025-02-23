"""the Ability To Duplicate

This is a proof-of-concept that brings together a few concepts:

- **Duplication**: copy geospatial data assets from one place to another. This might be across cloud providers, or to/from a local system.
- **Provenance**: use characteristics of the data to add metadata that helps users know the data are valid copies (e.g. checksums).
- **Discoverability**: create [STAC items](https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md) for each asset so we know what we copied, and store those items in a way that allows quick-and-easy search and discovery.

This documentation was generated directly from the source using [pycco](https://github.com/pycco-docs/pycco).
"""

from __future__ import annotations

import asyncio
import datetime
import time
import urllib.parse
from asyncio import Queue, TaskGroup
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import click

# **obstore** is a modern Python library that uses Rust under the hood for fast cross-cloud operations: <https://developmentseed.org/obstore/>
import obstore
import obstore.store

# If you know more about your assets, you might create more advanced STAC item generation. For this general case, we use [rio-stac](https://github.com/developmentseed/rio-stac).
import rio_stac

# [stacrs](https://github.com/stac-utils/stacrs) uses the same underlying Rust library as **obstore** for cross-cloud operations, and can read and write [stac-geoparquet](https://github.com/stac-utils/stac-geoparquet/blob/main/spec/stac-geoparquet-spec.md).
import stacrs
from multiformats import multihash
from pystac import Asset, Item
from rasterio import MemoryFile

if TYPE_CHECKING:
    # `ObjectStore` and `ObjectMeta` aren't actual Python classes, they're just
    # a type hints. We're working on making the documentation more clear on this
    # point: <https://github.com/developmentseed/obstore/issues/277>
    from obstore import ObjectMeta
    from obstore.store import ObjectStore


# This is a simple dataclass to represent a geospatial file that we will copy to our destination.
# More advanced implementations might have multiple files, e.g. in the case of a "granule".
@dataclass(frozen=True)
class SourceFile:
    href: str
    path: str
    extension: str | None
    id: str | None
    size: int

    # Creates a source file from an entry in a **obstore** `list` operation.
    @classmethod
    def from_entry(cls: type[SourceFile], source: str, entry: ObjectMeta) -> SourceFile:
        path = entry["path"]
        if "." in path:
            id, extension = path.rsplit(".", 1)
        else:
            id = None
            extension = None
        href = source.rstrip("/") + "/" + path
        return SourceFile(
            href=href, path=path, extension=extension, id=id, size=entry["size"]
        )

    # You could expand this to other file extensions, or do other checks.
    def should_be_copied(self) -> bool:
        return self.extension is not None and self.extension in ("tif", "tiff")

    def get_size_in_mb(self) -> str:
        return f"{self.size / 1_000_000:.2f} MB"


# A more advanced CLI would provide options for customizing the behavior of the operations. For now, we keep it simple.
@click.command
@click.argument("source")
@click.argument("destination")
def cli(source: str, destination: str) -> None:
    timeout = datetime.timedelta(minutes=10)
    source = to_url(source)
    source_store = obstore.store.from_url(url=source, timeout=timeout)  # type: ignore
    destination = to_url(destination)
    destination_store = obstore.store.from_url(destination)
    messages: Queue[str | None] = Queue()

    # There are plugins for **click** that simplify the ergonomics of async usage, but this internal function is good enough for our simple case.
    async def run() -> None:
        asyncio.create_task(print_messages(messages))
        tasks = []
        async with TaskGroup() as task_group:
            for source_file in get_source_files(source, source_store):
                tasks.append(
                    task_group.create_task(
                        copy(
                            source_file,
                            source_store,
                            destination,
                            destination_store,
                            messages,
                        )
                    )
                )

        items = [task.result().to_dict() for task in tasks]

        # The **stac-geoparquet** file is organized in a way that allows for easy search and discovery.
        # **stacrs** uses [DuckDB](https://duckdb.org/) under-the-hood to enable STAC API queries:
        #
        # ```python
        # items = await stacrs.search(
        #   "s3://my-bucket/items.parquet",
        #   intersects=...
        # )
        # ```
        #
        # You can also use **stacrs**'s command-line interface to serve the items in a simple STAC API server:
        #
        # ```shell
        # $ stacrs serve s3://my-bucket/items.parquet
        # ```
        #
        # You could then browse the items with [stac-browser](https://radiantearth.github.io/stac-browser/#/?.language=en).
        # See [the README](https://github.com/developmentseed/atd/blob/main/README.md) for a complete walkthrough.
        await messages.put("Putting items.geoparquet")
        geoparquet_path = destination.rstrip("/") + "/" + "items.geoparquet"
        await stacrs.write(geoparquet_path, items)
        await messages.put("Put items.geoparquet")

        # We use a `None` message to indicate that our message printing task should exit gracefully.
        await messages.put(None)

        print(f"Items are available at {geoparquet_path}")

    asyncio.run(run())


# In this case, we search for GeoTIFF files. If you know more about your domain,
# you might expand the type of file you're looking for, or have some other
# discovery mechanism.
def get_source_files(source: str, store: ObjectStore) -> Iterator[SourceFile]:
    for page in obstore.list(store):
        for entry in page:
            source_file = SourceFile.from_entry(source, entry)
            if source_file.should_be_copied():
                yield source_file


# **obstore** doesn't like relative paths, so we convert them to `file://`.
def to_url(s: str) -> str:
    if urllib.parse.urlparse(s).scheme:
        return s
    else:
        # This will fail for local filesystems if the path doesn't exist. If you
        # want to create the destination directory, add an option here to create
        # the directory.
        return "file://" + str(Path(s).absolute())


# Copying is a three step process:
#
# 1. Copy the data into local memory
# 2. Create a STAC item for the data
# 3. Copy the data to the destination location
#
# Because we know the size of the source object from original **obstore** list
# operation, we _could_ implement a memory cap on the amount of data we have
# locally. We haven't done that here.
async def copy(
    source_file: SourceFile,
    source_store: ObjectStore,
    destination: str,
    destination_store: ObjectStore,
    messages: Queue,
) -> Item:
    # A real-world implementation would have some sort of throttling to ensure
    # we don't request too many things at once.
    response = await obstore.get_async(source_store, source_file.path)
    data = b""

    await messages.put(f"Getting {source_file.path} ({source_file.get_size_in_mb()})")
    start = time.time()
    # We use async whenever we can to allow the scheduler to run other tasks while we're doing IO.
    data += bytes(await response.bytes_async())
    await messages.put(
        f"Got {source_file.path} ({source_file.get_size_in_mb()} in {time.time() - start:.2f}s)"
    )

    destination_href = destination.rstrip("/") + "/" + source_file.path
    await messages.put(f"Creating STAC item for {source_file.path}")
    start = time.time()
    item = create_item(data, source_file, destination_href)
    await messages.put(
        f"Created STAC item for {source_file.path} ({time.time() - start:.2f}s)"
    )

    await messages.put(f"Putting {source_file.path} ({source_file.get_size_in_mb()})")
    start = time.time()
    await obstore.put_async(destination_store, source_file.path, data)
    await messages.put(
        f"Put {source_file.path} ({source_file.get_size_in_mb()} MB in {time.time() - start:.2f}s)"
    )

    return item


# Creates a STAC item. This example is simple, but you could do a lot more work
# here, e.g. what is done in
# [stactools-packages](https://github.com/stactools-packages/).
def create_item(data: bytes, source_file: SourceFile, destination_href: str) -> Item:
    with MemoryFile(data) as memory_file:
        with memory_file.open() as dataset:
            item = rio_stac.create_stac_item(
                dataset,
                asset_href=destination_href,
                asset_roles=["data"],
                id=source_file.id,
                # We don't add raster information because it requires scanning the whole file again.
                with_eo=True,
                with_proj=True,
                with_raster=False,
            )
    checksum = multihash.digest(data, "sha2-256").hex()
    item.ext.add("file")
    asset = item.assets["asset"]
    asset.ext.file.checksum = checksum
    original = Asset(href=source_file.href)
    original.ext.file.checksum = checksum
    item.assets = {"data": asset, "original": original}
    return item


# A worker that simply prints messages to standard output. This could be
# customized for your use-case to, e.g., log messages to a structured logger or
# put notifications into a queue.
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
