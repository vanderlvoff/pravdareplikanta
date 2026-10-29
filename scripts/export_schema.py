"""Export the current editorial contract for file-based editorial handoff."""

import json
from pathlib import Path

from replicantpravda.models import Issue


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "content" / "issue.schema.json"
    path.write_text(
        json.dumps(Issue.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(path)
