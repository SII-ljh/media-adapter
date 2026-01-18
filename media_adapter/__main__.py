# -*- coding: utf-8 -*-
"""Allow running as: python -m media_adapter"""

from media_adapter.app import main, async_cleanup

if __name__ == "__main__":
    from media_adapter.utils.app_runner import run
    from media_adapter.app import crawler

    def _force_stop() -> None:
        c = crawler
        if not c:
            return
        cdp_manager = getattr(c, "cdp_manager", None)
        launcher = getattr(cdp_manager, "launcher", None)
        if not launcher:
            return
        try:
            launcher.cleanup()
        except Exception:
            pass

    run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)
