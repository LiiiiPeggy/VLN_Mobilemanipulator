"""Generate a uniformly scaled Habitat URDF without modifying the 1.0× pin.

################################
Scales: joint/link origin xyz, mesh scale attrs, box/cylinder/sphere sizes,
inertial origin xyz. Keeps rpy, axis directions, joint limits.
Uses regex rewrite because the stage410d pin contains ``--`` inside XML
comments (invalid for strict ElementTree, still loadable by Habitat/urdfdom).
################################
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

from .constants import URDF_HABITAT
from .robot_scale import ROBOT_SCALE_070, scaled_urdf_path


def _scale_xyz_string(raw: str, scale: float) -> str:
    parts = raw.replace(",", " ").split()
    if len(parts) != 3:
        return raw
    vals = [float(p) * scale for p in parts]
    return " ".join(f"{v:.12g}" for v in vals)


def scale_urdf_text(text: str, scale: float) -> str:
    s = float(scale)

    def repl_origin_xyz(m: re.Match) -> str:
        return m.group(1) + _scale_xyz_string(m.group(2), s) + m.group(3)

    # <origin ... xyz="a b c" ...>  (also inertial/visual/collision origins)
    text = re.sub(
        r'(<origin\b[^>]*\bxyz=")([^"]+)(")',
        repl_origin_xyz,
        text,
        flags=re.IGNORECASE,
    )

    def repl_mesh(m: re.Match) -> str:
        pre, raw, post = m.group(1), m.group(2), m.group(3)
        if raw.strip():
            parts = raw.replace(",", " ").split()
            if len(parts) == 3:
                vals = [float(p) * s for p in parts]
            else:
                vals = [s, s, s]
        else:
            vals = [s, s, s]
        return pre + " ".join(f"{v:.12g}" for v in vals) + post

    # Existing scale="..." (allow spaces around =)
    text = re.sub(
        r'(<mesh\b[^>]*\bscale\s*=\s*")([^"]*)(")',
        repl_mesh,
        text,
        flags=re.IGNORECASE,
    )

    # Inject scale into <mesh ...> that lack scale= (paths contain '/', so avoid [^>/]*)
    def inject_mesh_scale(m: re.Match) -> str:
        tag = m.group(0)
        if re.search(r"\bscale\s*=", tag, flags=re.IGNORECASE):
            return tag
        if tag.rstrip().endswith("/>"):
            return tag[:-2] + f' scale="{s:.12g} {s:.12g} {s:.12g}" />'
        if tag.endswith(">"):
            return tag[:-1] + f' scale="{s:.12g} {s:.12g} {s:.12g}">'
        return tag

    text = re.sub(r"<mesh\b[^>]*>", inject_mesh_scale, text, flags=re.IGNORECASE)

    def repl_box(m: re.Match) -> str:
        return m.group(1) + _scale_xyz_string(m.group(2), s) + m.group(3)

    text = re.sub(
        r'(<box\b[^>]*\bsize=")([^"]+)(")',
        repl_box,
        text,
        flags=re.IGNORECASE,
    )

    def repl_float_attr(m: re.Match) -> str:
        return m.group(1) + f"{float(m.group(2)) * s:.12g}" + m.group(3)

    text = re.sub(
        r'(<(?:cylinder|sphere)\b[^>]*\bradius=")([^"]+)(")',
        repl_float_attr,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'(<cylinder\b[^>]*\blength=")([^"]+)(")',
        repl_float_attr,
        text,
        flags=re.IGNORECASE,
    )
    return text


def ensure_scaled_urdf(
    scale: float = ROBOT_SCALE_070,
    *,
    src: Optional[str] = None,
    dst: Optional[str] = None,
    force: bool = False,
) -> str:
    src_p = Path(src or URDF_HABITAT)
    dst_p = Path(dst or scaled_urdf_path(scale))
    if dst_p.is_file() and not force:
        return str(dst_p)
    if not src_p.is_file():
        raise FileNotFoundError(f"source URDF missing: {src_p}")
    raw = src_p.read_text(encoding="utf-8", errors="replace")
    scaled = scale_urdf_text(raw, float(scale))
    note = (
        f"<!-- ################################\n"
        f"  Adapter-generated URDF scale={float(scale):.3f} from {src_p.name}.\n"
        f"  PROXY ONLY — not real Ranger+CR10 geometry. Tag scaled_robot_proxy_070.\n"
        f"################################ -->\n"
    )
    if scaled.lstrip().startswith("<?xml"):
        i = scaled.find("?>")
        scaled = scaled[: i + 2] + "\n" + note + scaled[i + 2 :]
    else:
        scaled = note + scaled
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    dst_p.write_text(scaled, encoding="utf-8")
    return str(dst_p)


def main() -> None:
    p = argparse.ArgumentParser(description="Write scaled Habitat URDF (adapter-only)")
    p.add_argument("--scale", type=float, default=ROBOT_SCALE_070)
    p.add_argument("--src", default=URDF_HABITAT)
    p.add_argument("--dst", default="")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    out = ensure_scaled_urdf(
        args.scale, src=args.src, dst=args.dst or None, force=args.force
    )
    print(out)


if __name__ == "__main__":
    main()
