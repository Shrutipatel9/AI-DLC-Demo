"""Journey fixtures: the report harness (full pipeline with fakes) plus the onboarding user.

Nothing here calls OpenAI, Stripe or a mail provider.
"""

from __future__ import annotations

from tests.onboarding.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    give_consent,
    user,
)
from tests.photos.conftest import upload  # noqa: F401
from tests.report.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    Harness,
    ImageHarness,
    app,
    client,
    consistent,
    email_fake,
    fake_gateway,
    harness,
    image_harness,
    insert_payment,
    make_paid_user,
    media_root,
    paid,
    run_to_done,
    seed_definition,
    settings_overrides,
    submitted,
    text_model,
    upload_consistent_set,
    webhooks,
)
