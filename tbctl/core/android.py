# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import re
import struct
from pathlib import Path

from tbctl.core.process import BuildError

SECTOR = 512

LP_RESERVED_BYTES = 4096
LP_GEOMETRY_MAGIC = 0x616C4467
LP_GEOMETRY_SIZE = 4096
LP_HEADER_MAGIC = 0x414C5030
LP_TARGET_TYPE_LINEAR, LP_TARGET_TYPE_ZERO = 0, 1
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def assemble_qfil_chunks(images: Path, partition_prefix: str, out: Path, size: int,
                         sector_size: int = 4096) -> int:
    xml = (images / "rawprogram_unsparse0.xml").read_text()
    chunks = [(f, int(s)) for f, s in re.findall(
        rf'filename="({partition_prefix}_\d+\.img)"[^>]*?start_sector="(\d+)"', xml)]
    if not chunks:
        raise BuildError(f"no {partition_prefix}_*.img chunks in rawprogram_unsparse0.xml")
    base = min(s for _, s in chunks)
    with open(out, "wb") as o:
        o.truncate(size)
        for name, start in chunks:
            o.seek((start - base) * sector_size)
            with open(images / name, "rb") as i:
                while block := i.read(1 << 24):
                    o.write(block)
    return len(chunks)


def _lp_partitions(f) -> dict[str, list[tuple[int, int, int]]]:
    f.seek(LP_RESERVED_BYTES)
    magic, _struct_size = struct.unpack("<II", f.read(8))
    if magic != LP_GEOMETRY_MAGIC:
        raise BuildError("not a super image (no liblp geometry)")
    f.seek(LP_RESERVED_BYTES + 2 * LP_GEOMETRY_SIZE)
    header = f.read(256)
    magic, _major, _minor, header_size = struct.unpack_from("<IHHI", header, 0)
    if magic != LP_HEADER_MAGIC:
        raise BuildError("no liblp metadata header")
    tables = struct.unpack_from("<12I", header, 12 + 32 + 4 + 32)
    (p_off, p_num, p_size), (e_off, e_num, e_size) = tables[0:3], tables[3:6]
    f.seek(LP_RESERVED_BYTES + 2 * LP_GEOMETRY_SIZE + header_size)
    blob = f.read(max(p_off + p_num * p_size, e_off + e_num * e_size))
    extents = [struct.unpack_from("<QIQI", blob, e_off + i * e_size)[:3] for i in range(e_num)]
    parts = {}
    for i in range(p_num):
        raw_name, _attrs, first, count, _group = struct.unpack_from("<36sIIII", blob, p_off + i * p_size)
        parts[raw_name.rstrip(b"\0").decode()] = extents[first:first + count]
    return parts


def extract_logical_partition(super_img: Path, names: list[str], out: Path) -> str:
    with open(super_img, "rb") as f:
        parts = _lp_partitions(f)
        name = next((n for n in names if n in parts), None)
        if name is None:
            raise BuildError(f"none of {names} in super (has: {', '.join(sorted(parts))})")
        with open(out, "wb") as o:
            for num_sectors, target_type, target_data in parts[name]:
                size = num_sectors * SECTOR
                if target_type == LP_TARGET_TYPE_ZERO:
                    o.seek(size, 1)
                    continue
                if target_type != LP_TARGET_TYPE_LINEAR:
                    raise BuildError(f"{name}: unsupported extent type {target_type}")
                f.seek(target_data * SECTOR)
                while size:
                    block = f.read(min(size, 1 << 24))
                    o.write(block)
                    size -= len(block)
            o.truncate()
    return name


def split_dtbs(blob: bytes, skip: int = 0) -> list[bytes]:
    dtbs, i = [], skip
    while (j := blob.find(FDT_MAGIC, i)) >= 0:
        size = struct.unpack(">I", blob[j + 4:j + 8])[0]
        if size < 100 or j + size > len(blob):
            i = j + 4
            continue
        dtbs.append(blob[j:j + size])
        i = j + size
    return dtbs
