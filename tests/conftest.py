from __future__ import annotations

import pytest

import yasli_scraper.__main__ as scraper_main


@pytest.fixture(autouse=True)
def _isolate_repo_env(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Point REPO_ENV_PATH at a nonexistent file so the real repo-root .env
    # (if any) never bleeds into tests. Tests that exercise dotenv loading
    # override this with their own path.
    nowhere = tmp_path_factory.mktemp("no-dotenv") / ".env"
    monkeypatch.setattr(scraper_main, "REPO_ENV_PATH", nowhere)
