"""Score the extraction agents on whether they invent things.

Runs Rx, Labs, Forensics or Scribe over a case set and writes the report to
eval/reports/. The property measured is the one all four share: every claim
carries a span, and that span either occurs in the source or it does not.

**What a good score means, and what it does not.** A fabrication rate of zero
shows the agent invented nothing on these cases. It does not show the agent
found the right things, or that the things it found matter clinically. That
needs a clinician and a reference set which does not exist; the report says so
in its own text so a reader cannot take it for more than it is.

Case sets live in `services/<service>/eval/cases/groundedness.json`. Each case
is a source document and, optionally, the spans a reference says are in it.
Cases without reference spans still score fabrication and are counted
separately, so a reader can see how much of the set is unscored.

Run:
    python scripts/run_groundedness_eval.py --service rx
    python scripts/run_groundedness_eval.py --service rx --out eval/reports/rx.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spine.eval.harness import AgentOutcome, Case, as_json, load_cases, run
from spine.inference.config import (
    InferenceConfig,
    assert_transport_is_permitted,
    model_spec,
)
from spine.inference.ollama import OllamaProvider
from spine.inference.prompts import load

EVAL_TIMEOUT_SECONDS: Final[float] = 600.0
"""Longer than a patient turn, because nobody is waiting on an eval run."""

AGENTS: Final[dict[str, str]] = {
    "rx": "reading_agent",
    "labs": "extraction_agent",
    "forensics": "structuring_agent",
    "scribe": "note_agent",
}
"""The extraction agent each service exposes to this eval.

Consult is absent deliberately. Its structuring agent is scored the same way,
but Consult's own harness scores it against triage outcomes as well, and
running it here would report a second number for the same thing.
"""


def runner_for(service: str, provider: OllamaProvider, model: str):  # type: ignore[no-untyped-def]
    """Adapt one service's agent to the harness's shape.

    Every kept claim is scored on its provenance span rather than on a
    rendered field, because the span is what the builder verified against the
    source and is therefore the thing this eval is checking. A rendered field
    may be normalised — a molecule name lowercased, a value reformatted — and
    would fail a substring check that the agent did nothing wrong to fail.
    """
    # Imported per service rather than at module level: a run for one service
    # should not pull in the other three, and Scribe's chain reaches torch.
    prompt = load(service, AGENTS[service])

    if service == "rx":
        from services.rx.agents.reading_agent import read  # noqa: PLC0415
        from services.rx.agents.resolver import BrandIndex  # noqa: PLC0415

        def rx(case: Case) -> AgentOutcome:
            built = read(
                provider,
                prompt,
                model,
                case.source,
                source_id=case.case_id,
                index=BrandIndex(),
            )
            return AgentOutcome(
                kept_spans=_spans(built.medications.medications),
                dropped=built.fabrication_count,
            )

        return rx

    if service == "labs":
        from services.labs.agents.extraction_agent import extract  # noqa: PLC0415

        def labs(case: Case) -> AgentOutcome:
            built = extract(provider, prompt, model, case.source, case.case_id)
            return AgentOutcome(
                kept_spans=_spans(built.results), dropped=built.fabrication_count
            )

        return labs

    if service == "forensics":
        from services.forensics.agents.structuring_agent import structure  # noqa: PLC0415

        def forensics(case: Case) -> AgentOutcome:
            built = structure(
                provider,
                prompt,
                model,
                dictation=case.source,
                source_id=case.case_id,
                examiner_id="eval",
            )
            return AgentOutcome(
                kept_spans=_spans(built.injuries), dropped=built.fabrication_count
            )

        return forensics

    from services.scribe.agents.note_agent import draft_note  # noqa: PLC0415
    from spine.schemas.transcript import Speaker, Transcript, TranscriptSegment  # noqa: PLC0415

    def scribe(case: Case) -> AgentOutcome:
        # Scribe reads a diarised transcript rather than raw text. One segment
        # attributed to nobody is the honest shape for an eval case: the
        # groundedness property does not depend on who spoke.
        transcript = Transcript(
            segments=(
                TranscriptSegment(
                    text=case.source,
                    speaker=Speaker.UNKNOWN,
                    audio_start_ms=0,
                    audio_end_ms=max(1, len(case.source) * 50),
                ),
            )
        )
        built = draft_note(provider, prompt, model, transcript, case.case_id)
        return AgentOutcome(
            kept_spans=_spans(built.statements), dropped=built.fabrication_count
        )

    return scribe


def _spans(claims: object) -> tuple[str, ...]:
    """The verified source span behind each kept claim.

    An ExaminerEntry has no span — a human wrote it — and is skipped rather
    than scored, because there is nothing for it to be grounded in.
    """
    found: list[str] = []
    for claim in claims:  # type: ignore[attr-defined]
        provenance = getattr(claim, "provenance", None)
        text = getattr(provenance, "text", None)
        if isinstance(text, str) and text:
            found.append(text)
    return tuple(found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True, choices=sorted(AGENTS))
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    cases_path = args.cases or Path(
        f"services/{args.service}/eval/cases/groundedness.json"
    )
    cases = load_cases(cases_path)

    config = InferenceConfig.from_environment()
    assert_transport_is_permitted(config)
    model_spec(config)
    provider = OllamaProvider(timeout=EVAL_TIMEOUT_SECONDS)

    agent = AGENTS[args.service]
    print(f"{agent}: {len(cases)} case(s)", flush=True)
    report = run(agent, cases, runner_for(args.service, provider, config.primary_model))

    document = as_json(report)
    document["service"] = args.service
    document["model"] = config.primary_model
    document["run_on"] = str(date.today())

    out = args.out or Path(f"eval/reports/{date.today()}-{args.service}-groundedness.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2), encoding="utf-8")

    print(f"  fabrication rate: {report.fabrication_rate:.1%}")
    if report.recall is None:
        print("  recall: not scored — no case in this set carries reference spans")
    else:
        print(f"  recall: {report.recall:.1%} over {len(report.scored_for_recall)} case(s)")
    if report.unscored_count:
        print(f"  {report.unscored_count} case(s) unscored for recall")
    print(f"\nwrote {out}")
    print(
        "\nThis measures fabrication and span recall. It does not measure whether "
        "what the agent found was clinically the right thing to find."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
