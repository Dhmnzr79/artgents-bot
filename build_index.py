import argparse
import glob
import os

import frontmatter
from dotenv import load_dotenv

from core.client_runtime import client_md_dir, list_buildable_client_ids
from core.content_linter import format_lint_report, lint_all_clients
from core.md_chunks import split_md_to_chunks

# --- logging (устойчиво) ---
try:
    from logging_setup import log_json, setup_logging
except Exception:
    import logging
    import json as _json

    def log_json(logger, msg, **fields):
        try:
            logger.info(f"{msg} " + _json.dumps(fields, ensure_ascii=False))
        except Exception:
            logger.info(msg)

    def setup_logging():
        logger = logging.getLogger("builder")
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
        return logger


logger = setup_logging()

load_dotenv()


def build_client_index(client_id: str) -> None:
    md_root = client_md_dir(client_id)
    chunks_count = 0

    pattern = os.path.join(md_root, "**", "*.md")
    paths = sorted(glob.glob(pattern, recursive=True))
    if not paths:
        log_json(logger, "index_build_skip_empty", client_id=client_id, md_root=md_root)
        return

    for path in paths:
        with open(path, "r", encoding="utf-8-sig") as fh:
            fm = frontmatter.load(fh)
        chunks_count += len(split_md_to_chunks(fm.content))

    log_json(
        logger,
        "Content build check completed",
        client_id=client_id,
        chunks_count=chunks_count,
        md_files=len(paths),
    )
    print(f"OK [{client_id}]: md_files={len(paths)}, chunks={chunks_count}")


def main():
    parser = argparse.ArgumentParser(description="Validate per-client markdown content")
    parser.add_argument(
        "--client",
        default="all",
        help="Client pack id (demo) or 'all'",
    )
    parser.add_argument(
        "--skip-lint",
        action="store_true",
        help="Skip content linter (not recommended)",
    )
    args = parser.parse_args()
    if args.client == "all":
        targets = list_buildable_client_ids()
    else:
        targets = [args.client.strip()]
    if not args.skip_lint:
        lint_results = lint_all_clients(targets)
        if any(not r.ok for r in lint_results):
            print(format_lint_report(lint_results), file=__import__("sys").stderr)
            raise SystemExit("Content lint failed; fix md or use --skip-lint")
    log_json(logger, "Starting index build", clients=targets)
    for cid in targets:
        build_client_index(cid)


if __name__ == "__main__":
    main()
