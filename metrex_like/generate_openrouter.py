"""
Generate candidate PennyLane code for kept samples via OpenRouter,
then score with run_verithoughts_loop.py.

Setup:
  1. Copy .env.example to .env in this folder (already created).
  2. Put your OpenRouter key in .env:
       OPENROUTER_API_KEY=sk-or-...
  3. pip install openai

Small test (recommended first):
  python generate_openrouter.py \\
    --kept filter_out/pennysynth_full/kept.jsonl \\
    --limit 10 \\
    --model openai/gpt-4o-mini

Then score:
  python run_verithoughts_loop.py \\
    --kept filter_out/pennysynth_full/kept.jsonl \\
    --predictions filter_out/pennysynth_full/preds_openrouter.jsonl \\
    --limit 10 \\
    --out filter_out/pennysynth_full/loop_openrouter.jsonl

Or do both in one go:
  python generate_openrouter.py --kept ... --limit 10 --score
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SYSTEM_PROMPT = """You write PennyLane quantum circuits in Python.
Return ONLY runnable Python code (no markdown fences, no explanation).
Requirements:
- Use pennylane as qml
- Define a @qml.qnode on default.qubit (or lightning.qubit)
- The QNode should implement the requested circuit and return a measurement or state
- Keep the circuit self-contained and small enough to run
"""


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def strip_code_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:python|py)?\s*\n([\s\S]*?)\n```\s*$", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    # Soft strip if model added fences plus trailing chatter
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            body = parts[1]
            if body.lstrip().lower().startswith(("python", "py")):
                body = body.split("\n", 1)[-1]
            return body.strip()
    return text


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def load_api_key(env_file: Path | None = None) -> str:
    """Read OPENROUTER_API_KEY from a .env file, then from the environment."""
    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(env_file)
    here = Path(__file__).resolve().parent
    candidates.extend(
        [
            here / ".env",
            here.parent / ".env",
            here.parents[1] / ".env",
        ]
    )
    for path in candidates:
        values = _parse_env_file(path)
        key = values.get("OPENROUTER_API_KEY") or values.get("OPENAI_API_KEY")
        if key:
            return key
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""


def make_client(env_file: Path | None = None):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install the OpenAI client: pip install openai") from exc

    api_key = load_api_key(env_file)
    if not api_key:
        default = Path(__file__).resolve().parent / ".env"
        raise SystemExit(
            "Missing OPENROUTER_API_KEY.\n"
            f"Put it in {default} as:\n"
            "  OPENROUTER_API_KEY=sk-or-...\n"
            "Do not commit that file."
        )
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def generate_one(client, model: str, instruction: str, temperature: float) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Write PennyLane code for this task:\n\n"
                    f"{instruction}\n\n"
                    "Return only Python code."
                ),
            },
        ],
    )
    content = resp.choices[0].message.content or ""
    return strip_code_fence(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kept", type=str, required=True)
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Predictions jsonl path (default: alongside kept as preds_openrouter.jsonl)",
    )
    parser.add_argument("--model", type=str, default="openai/gpt-4o-mini")
    parser.add_argument("--limit", type=int, default=10, help="How many kept samples to try")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--sleep", type=float, default=0.3, help="Pause between API calls")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip ids already present in --out",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="After generation, run run_verithoughts_loop.py on the same ids",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to .env containing OPENROUTER_API_KEY (default: this folder's .env)",
    )
    args = parser.parse_args()

    kept_path = Path(args.kept)
    kept = load_jsonl(kept_path)
    kept = kept[args.offset : args.offset + args.limit]

    out_path = Path(args.out) if args.out else kept_path.parent / "preds_openrouter.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done: dict[str, dict] = {}
    if args.resume and out_path.exists():
        for row in load_jsonl(out_path):
            if row.get("id") is not None:
                done[str(row["id"])] = row

    env_file = Path(args.env_file) if args.env_file else None
    client = make_client(env_file)
    print(f"Model={args.model}  samples={len(kept)}  out={out_path}", flush=True)

    rows_out: list[dict] = list(done.values())
    # Keep deterministic order by rewriting file as we go.
    by_id = dict(done)

    for i, row in enumerate(kept, 1):
        sid = str(row["id"])
        instruction = row.get("instruction") or ""
        if sid in by_id and by_id[sid].get("code"):
            print(f"[{i}/{len(kept)}] skip existing {sid}", flush=True)
            continue
        try:
            code = generate_one(client, args.model, instruction, args.temperature)
            rec = {
                "id": sid,
                "model": args.model,
                "instruction": instruction,
                "code": code,
            }
            print(f"[{i}/{len(kept)}] ok {sid}  code_len={len(code)}", flush=True)
        except Exception as exc:  # noqa: BLE001
            rec = {
                "id": sid,
                "model": args.model,
                "instruction": instruction,
                "code": "",
                "error": str(exc),
            }
            print(f"[{i}/{len(kept)}] FAIL {sid}: {exc}", flush=True)

        by_id[sid] = rec
        rows_out = list(by_id.values())
        with out_path.open("w", encoding="utf-8") as f:
            for r in rows_out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        time.sleep(args.sleep)

    n_ok = sum(1 for r in by_id.values() if r.get("code"))
    print(f"Wrote {out_path}  ({n_ok} with code / {len(by_id)} rows)")

    if args.score:
        loop_out = out_path.with_name("loop_openrouter.jsonl")
        cmd = [
            sys.executable,
            str(Path(__file__).with_name("run_verithoughts_loop.py")),
            "--kept",
            str(kept_path),
            "--predictions",
            str(out_path),
            "--out",
            str(loop_out),
        ]
        # Score only the slice we generated: pass matching limit/offset via filtering file.
        # Simplest: write a tiny kept slice for scoring.
        slice_kept = out_path.with_name("kept_slice_for_score.jsonl")
        with slice_kept.open("w", encoding="utf-8") as f:
            for row in kept:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        cmd[cmd.index("--kept") + 1] = str(slice_kept)
        print("Scoring with QCEC...", flush=True)
        subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
