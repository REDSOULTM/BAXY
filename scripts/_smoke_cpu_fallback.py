"""Smoke del fallback-CPU (sin arrancar server ni input sintetico): valida que el
perfil `cpu` exista con -ngl 0 / vision OFF / sin mmproj, que llama_command ponga
-ngl 0 y NO los flags CUDA-crash en CPU, que el watcher baje a `cpu` por default,
y que launcher + agent_runner importen limpio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gemma4_agent.infra.profiles import PROFILES, Profile, get_active_profile

assert "cpu" in PROFILES, "falta perfil cpu"
cpu = PROFILES["cpu"]
assert cpu.n_gpu_layers == 0, f"cpu n_gpu_layers={cpu.n_gpu_layers}"
assert cpu.vision_enabled is False, "cpu vision debe estar OFF"
assert cpu.mmproj_path is None, "cpu no debe cargar mmproj"
assert "n_gpu_layers" in Profile.__dataclass_fields__
print("[1] profiles OK: cpu -ngl=0, vision OFF, mmproj None")

from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.config import AgentConfig

cfg = AgentConfig.from_env()
cmd_cpu = " ".join(str(x) for x in llama_command(cfg, cpu))
gpu = PROFILES.get("vram4") or get_active_profile()
cmd_gpu = " ".join(str(x) for x in llama_command(cfg, gpu))
assert "-ngl 0" in cmd_cpu, f"cpu sin -ngl 0: {cmd_cpu[:200]}"
assert "--ctx-checkpoints 0" not in cmd_cpu, "cpu NO debe tener flags CUDA-crash"
assert (int(gpu.n_gpu_layers) > 0), f"gpu deberia tener ngl>0, es {gpu.n_gpu_layers}"
print(f"[2] llama_command OK: cpu tiene -ngl 0 sin flags CUDA; gpu ngl={gpu.n_gpu_layers}")

from gemma4_agent.infra.profile_watcher import WatcherConfig

wc = WatcherConfig()
assert wc.downgrade_to == "cpu", f"downgrade_to={wc.downgrade_to}"
print(f"[3] profile_watcher OK: downgrade_to={wc.downgrade_to!r}")

import gemma4_agent.infra.launcher as L
import gemma4_agent.agent_core.agent_runner as R

assert hasattr(L, "run_ui")
print("[4] launcher + agent_runner importan limpio")
print("SMOKE PYTHON: OK")
