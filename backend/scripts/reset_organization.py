"""
Reset all org-scoped runtime data for a single organization.

Run from backend/:
    python -m scripts.reset_organization <organization_id>

This keeps the schema intact and only deletes data rows tied to the provided org:
documents, chunks, embeddings, gaps, conversations, messages, citations, and query logs.
"""

import argparse
import asyncio
import json
import uuid

from src.database import AsyncSessionLocal
from src.services.reset_organization_service import reset_organization_data


async def _run(organization_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        result = await reset_organization_data(db, organization_id)

    print(json.dumps(result, indent=2, default=str))

    remaining = result["remaining"]
    if any(value != 0 for value in remaining.values()):
        raise SystemExit("Reset incompleto: todavia quedan registros para la organizacion.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete all org-scoped runtime data for testing.")
    parser.add_argument("organization_id", type=uuid.UUID, help="Organization UUID to reset")
    args = parser.parse_args()
    asyncio.run(_run(args.organization_id))


if __name__ == "__main__":
    main()
