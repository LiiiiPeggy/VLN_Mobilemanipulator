"""Standalone Habitat EE RGB-D renderer (run inside vln-apexnav)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import magnum as mn
import numpy as np
from PIL import Image
import habitat_sim


def save_depth_mm(path: Path, depth: np.ndarray) -> None:
    d = np.clip(depth * 1000.0, 0, 65535).astype(np.uint16)
    Image.fromarray(d).save(path)


def main(out_dir: str, poses_json: str, scene: str, gpu: int = 0) -> None:
    out = Path(out_dir)
    records = json.loads(Path(poses_json).read_text())
    for sub in ("rgb_ee", "depth_ee", "third_habitat"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = scene
    backend.enable_physics = False
    backend.gpu_device_id = gpu

    def make(uuid, depth=False, res=(480, 640), hfov=79.0):
        s = habitat_sim.CameraSensorSpec()
        s.uuid = uuid
        s.sensor_type = habitat_sim.SensorType.DEPTH if depth else habitat_sim.SensorType.COLOR
        s.resolution = list(res)
        s.hfov = float(hfov)
        return s

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [
        make("ee_rgb"),
        make("ee_depth", depth=True),
        make("third_rgb", hfov=90.0),
    ]
    sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent_cfg]))
    agent = sim.get_agent(0)

    for rec in records:
        st = habitat_sim.AgentState()
        st.position = np.array(rec["camera_pos_habitat"], dtype=np.float32)
        w, x, y, z = rec["camera_wxyz_habitat"]
        # habitat_sim expects xyzw coeffs list (w last)
        st.rotation = np.array([x, y, z, w], dtype=np.float32)
        agent.set_state(st, infer_sensor_states=True)
        obs = sim.get_sensor_observations()
        i = rec["i"]
        Image.fromarray(obs["ee_rgb"][..., :3]).save(out / "rgb_ee" / f"frame_{i:04d}.png")
        save_depth_mm(out / "depth_ee" / f"frame_{i:04d}.png", obs["ee_depth"])
        Image.fromarray(obs["third_rgb"][..., :3]).save(out / "third_habitat" / f"frame_{i:04d}.png")
        d = obs["ee_depth"]
        rec["depth_stats"] = {
            "min": float(np.min(d)),
            "max": float(np.max(d)),
            "mean": float(np.mean(d)),
        }

    summary = {
        "status": "ok_habitat_pass",
        "habitat_sim": habitat_sim.__version__,
        "built_with_bullet": bool(habitat_sim.built_with_bullet),
        "scene": scene,
        "n": len(records),
        "out_dir": out_dir,
    }
    Path(poses_json).write_text(json.dumps(records, indent=2))
    (out / "summary_habitat.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    sim.close()


if __name__ == "__main__":
    out_dir = sys.argv[1]
    poses = sys.argv[2]
    scene = sys.argv[3]
    gpu = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    main(out_dir, poses, scene, gpu)
