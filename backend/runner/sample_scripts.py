"""
Generate side-by-side sample scripts for two niches on the same topic.

    cd backend && python -m runner.sample_scripts --topic "The Dyatlov Pass incident"

Loads profiles straight from app/niches/profiles.json (no DB needed) and
API keys from the environment ({PROVIDER}_API_KEY, e.g. GEMINI_API_KEY —
the repo .env is loaded automatically by the app package). This is a dev
tool: real jobs go through runner.script_stage with vault keys.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.niches.seed import load_profiles_file
from runner.llm_adapter import HOOK_STYLE_RULES, Provider, generate_script
from runner.style_judge import judge_hook_contrast

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "core" / "output_v2" / "sample_scripts"


def env_key_lookup(provider: Provider) -> dict[str, str] | None:
    value = os.environ.get(f"{provider.value.upper()}_API_KEY")
    return {"api_key": value} if value else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--niche", action="append", dest="niches",
                        help="niche id; repeatable (default: true_crime_narration, whatif_hypothetical)")
    parser.add_argument("--format", default="short", choices=["short", "long"])
    parser.add_argument("--order", default=None, help="comma-separated provider fallback order")
    parser.add_argument("--judge", action="store_true", help="also run the hook-style LLM judge on the first two scripts")
    args = parser.parse_args()

    niche_ids = args.niches or ["true_crime_narration", "whatif_hypothetical"]
    profiles = {p.id: p for p in load_profiles_file()}

    scripts = []
    for niche_id in niche_ids:
        profile = profiles[niche_id]
        script = generate_script(profile, args.topic, args.format,
                                 key_lookup=env_key_lookup, order=args.order)
        scripts.append((profile, script))

        print(f"\n{'=' * 78}")
        print(f"{profile.display_name}  ({script.provider.value} / {script.model}, "
              f"{len(script.scenes)} scenes, ~{script.estimated_duration_seconds:.0f}s, "
              f"needs_tts={script.needs_tts})")
        for attempt in script.failed_attempts:
            print(f"  [fallback] {attempt.message}")
        print("=" * 78)
        for i, scene in enumerate(script.scenes, 1):
            print(f"\nSCENE {i}")
            print(f"  SPEECH: {scene.speech}")
            print(f"  VISUAL: {scene.visual}")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / f"{niche_id}.txt"
        out.write_text(
            "\n\n".join(f"SCENE {i}\nSPEECH: {s.speech}\nVISUAL: {s.visual}"
                        for i, s in enumerate(script.scenes, 1)),
            encoding="utf-8",
        )
        print(f"\n(saved to {out})")

    if args.judge and len(scripts) >= 2:
        (profile_a, script_a), (profile_b, script_b) = scripts[0], scripts[1]
        verdict = judge_hook_contrast(
            script_a, HOOK_STYLE_RULES[profile_a.hook_style],
            script_b, HOOK_STYLE_RULES[profile_b.hook_style],
            key_lookup=env_key_lookup, order=args.order,
        )
        print(f"\n{'=' * 78}\nJUDGE ({verdict.provider.value}): {verdict.verdict}\nREASON: {verdict.reason}")


if __name__ == "__main__":
    main()
