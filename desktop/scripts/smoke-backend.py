"""Exercise a frozen backend, then restart it to verify SQLite persistence.

Only the Python standard library is used by the smoke driver. The child runs
from a temporary directory, with no Python/Node installation on its Windows
PATH, and must use the bundled frontend, migrations and scientific libraries.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import io
import json
import math
import os
from pathlib import Path
import queue
import secrets
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
import zipfile


class Backend:
    def __init__(self, port: int, token: str):
        self.base_url = f"http://127.0.0.1:{port}"
        self.token = token
        self.opener = build_opener(ProxyHandler({}))

    def request(self, path: str, data=None, *, method=None, authenticated=True):
        headers = {"X-CBOS-Token": self.token} if authenticated else {}
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        with self.opener.open(request, timeout=120) as response:
            return response.read()

    def json(self, path: str, data=None, **kwargs):
        return json.loads(self.request(path, data, **kwargs))


@contextmanager
def launch(executable: Path, data_dir: Path, output: Path, run_name: str):
    token = secrets.token_hex(32)
    environment = os.environ.copy()
    environment.update({"CBOS_DESKTOP_DATA_DIR": str(data_dir), "CBOS_DESKTOP_TOKEN": token})
    if os.name == "nt":
        # The executable must not accidentally load an installed Python/Node.
        environment["PATH"] = str(Path(environment["SystemRoot"]) / "System32")
    lines = queue.Queue()
    with (output / f"backend-{run_name}.log").open("wb") as log:
        process = subprocess.Popen(
            [str(executable)], cwd=data_dir.parent, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
        )

        def read_stdout():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        threading.Thread(target=read_stdout, daemon=True).start()
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    line = lines.get(timeout=min(1, max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                if line is None:
                    raise RuntimeError(f"Backend exited before ready; see backend-{run_name}.log")
                try:
                    ready = json.loads(line)
                except (ValueError, UnicodeDecodeError) as error:
                    raise RuntimeError("Backend stdout must contain only protocol JSON") from error
                if ready.get("type") == "ready":
                    assert "token" not in ready, "Ready message must not reveal its token"
                    port = ready["port"]
                    assert isinstance(port, int) and 0 < port < 65536
                    yield Backend(port, token)
                    break
            else:
                raise TimeoutError(f"Backend did not become ready; see backend-{run_name}.log")
        finally:
            # This is the production parent-lifetime protocol, not a force kill.
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError("Backend failed to stop after parent stdin closed")
            process.stdout.close()
        assert process.returncode == 0, f"Backend exit code: {process.returncode}"


def run_smoke(executable: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="CBOS smoke 测试 ") as temporary:
        data_dir = Path(temporary) / "user data"
        selected_ids = [1, 2, 5, 6, 7, 8]
        with launch(executable, data_dir, output, "first") as backend:
            try:
                backend.request("/health", authenticated=False)
                raise AssertionError("Unauthenticated request was accepted")
            except HTTPError as error:
                assert error.code in (401, 403), error.code
            health = backend.json("/health")
            assert health["status"] == "ok" and health["storage_mode"] == "sqlite"
            html = backend.request("/").decode("utf-8")
            assert "assets/" in html and "前端尚未构建" not in html
            coals = backend.json("/api/coals?page_size=0")["data"]
            by_id = {coal["id"]: coal for coal in coals}
            assert all(coal_id in by_id for coal_id in selected_ids)
            assert [by_id[item]["type"] for item in selected_ids].count("无烟煤") == 3
            assert [by_id[item]["type"] for item in selected_ids].count("烟煤") == 3
            constraints = {
                "heat_min": 0, "heat_max": 10000, "ash_min": 0, "ash_max": 100,
                "volatile_min": 0, "volatile_max": 100,
                "fixed_carbon_min": 0, "fixed_carbon_max": 100,
                "sulfur_min": 0, "sulfur_max": 10,
                "price_min": 0, "price_max": 5000,
                "ratio_constraints": {str(item): {"min": 5, "max": 60} for item in selected_ids},
            }
            result = backend.json("/api/optimization", {
                "selected_coal_ids": selected_ids,
                "calculation_mode": "screening", "ratio_basis": "unknown",
                "constraints": constraints,
                "ga_params": {"population_size": 24, "max_generations": 8,
                              "early_stopping_patience": 4, "random_seed": 42},
            })
            assert result["status"] == "success", result
            assert result["history_saved"] is True
            solution = result["result"]
            ratios = solution["optimal_ratios"]
            assert solution["is_feasible"] and len(ratios) == 6
            assert math.isclose(sum(ratios), 1, abs_tol=1e-8)
            assert all(0.05 - 1e-8 <= ratio <= 0.60 + 1e-8 for ratio in ratios)
            for result_key, coal_key in (("total_price", "price"), ("total_heat", "calorific_value")):
                expected = sum(ratio * by_id[item][coal_key] for item, ratio in zip(selected_ids, ratios))
                assert math.isclose(solution[result_key], expected, rel_tol=1e-8, abs_tol=1e-6)
            history = backend.json("/api/optimization/history")["data"]
            assert len(history) == 1
            history_id = history[0]["id"]
            report = backend.request(f"/api/optimization/export/{history_id}")
            with zipfile.ZipFile(io.BytesIO(report)) as workbook:
                assert "xl/workbook.xml" in workbook.namelist()
            (output / "optimization-report.xlsx").write_bytes(report)
            new_coal = {
                "name": "离线持久化测试煤", "type": "烟煤", "supplier": "Desktop CI",
                "price": 620, "calorific_value": 6200, "ash_content": 10,
                "volatile_matter": 20, "fixed_carbon": 65, "total_sulfur": 0.6,
                "moisture": 8.5, "mad": 1.2,
            }
            created = backend.json("/api/coals", new_coal)
            assert created["status"] == "success", created
            new_id = created["coal_id"]
            new_coal["price"] = 630
            updated = backend.json(f"/api/coals/{new_id}", new_coal, method="PUT")
            assert updated["status"] == "success", updated

        with launch(executable, data_dir, output, "restart") as backend:
            restored = backend.json(f"/api/coals/{new_id}")["data"]
            assert restored["name"] == new_coal["name"] and restored["price"] == 630
            persisted = backend.json(f"/api/optimization/history/{history_id}")["data"]
            assert persisted["result_payload"]["input_snapshot"] == result["input_snapshot"]
            assert persisted["result_payload"]["result"]["optimal_ratios"] == ratios
            assert len(backend.json("/api/coals?page_size=0")["data"]) == len(coals) + 1
        return {
            "status": "passed", "executable": str(executable),
            "selected_coal_ids": selected_ids, "initial_coal_count": len(coals),
            "optimal_ratios": ratios, "total_price": solution["total_price"],
            "total_heat": solution["total_heat"], "history_id": history_id,
            "restart_persistence": True, "xlsx_export": True,
            "parent_eof_shutdown": True, "unauthenticated_rejected": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("desktop/smoke-output/backend"))
    args = parser.parse_args()
    report = run_smoke(args.executable.resolve(strict=True), args.output.resolve())
    (args.output / "smoke-backend.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
