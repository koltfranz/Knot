"""生成单文件程序 dist/knot.pyz（供一键运行与 Release 附件使用）。"""

from __future__ import annotations

import shutil
import sys
import zipapp
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "src"
    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    sys.path.insert(0, str(source))
    from knot.version import __version__

    target = dist / f"knot-{__version__}.pyz"
    zipapp.create_archive(
        source,
        target=target,
        main="knot.cli.main:main",
        filter=lambda path: "__pycache__" not in path.parts,
        compressed=True,
    )
    shutil.copyfile(target, dist / "knot.pyz")

    size = target.stat().st_size
    print(f"已生成 {target}（{size / 1024:.0f} KB）")
    print(f"已生成 {dist / 'knot.pyz'}")
    print(f"运行方式：python {target.name} 记 38 餐饮 -f 现金")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
