#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--static", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    root = Path(__file__).resolve().parents[1]
    vendor = root / "vendor/idba"
    archive = vendor / "idba-1.1.3.tar.gz"
    expected = "6b1746a29884f4fa17b110d94d9ead677ab5557c084a93b16b6a043dbb148709"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit("IDBA source archive checksum mismatch")
    compiler = os.environ.get("CXX", "g++")
    for tool in (compiler, "patch"):
        if shutil.which(tool) is None:
            raise SystemExit(f"Program not found: {tool}")
    with tempfile.TemporaryDirectory(prefix="fevir-idba-") as tmp:
        build = Path(tmp)
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                dest = (build / member.name).resolve()
                if build not in dest.parents or member.issym() or member.islnk():
                    raise SystemExit("Invalid member in IDBA archive")
            source.extractall(build)
        source = build / "idba-1.1.3"
        subprocess.run(["patch", "-p1", "-i", str(vendor / "single-end.patch")], cwd=source, check=True)
        makefile = (source / "lib/Makefile.am").read_text().split("libgtest_a_SOURCES", 1)[0]
        sources = re.findall(r"\$\(top_srcdir\)/(src/\S+\.cpp)", makefile)
        flags = ["-std=gnu++11", "-O3", "-fopenmp", "-pthread", "-I", str(source / "src")]

        def compile_one(relative):
            obj = build / (relative.replace("/", "_") + ".o")
            subprocess.run([compiler, *flags, "-c", str(source / relative), "-o", str(obj)], check=True)
            return str(obj)

        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            objects = list(pool.map(compile_one, sources))
        link_flags = ["-static"] if args.static else []
        outputs = []
        for name in ("idba_ud", "fq2fa"):
            output = build / name
            subprocess.run([compiler, *flags, *link_flags, str(source / f"src/release/{name}.cpp"),
                            *objects, "-o", str(output)], check=True)
            outputs.append(output)
        subprocess.run([str(outputs[0]), "--version"], check=True)
        (root / "bin").mkdir(exist_ok=True)
        for output in outputs:
            shutil.copy2(output, root / "bin" / output.name)
        print(f"Installed idba_ud and fq2fa in {root / 'bin'}")


if __name__ == "__main__":
    main()
