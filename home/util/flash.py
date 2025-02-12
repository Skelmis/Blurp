from typing import Literal

from litestar.plugins.flash import flash


def alert(
    request,
    message,
    level: Literal["info", "warning", "error", "success"] = "info",
):
    """A helper function given we hard code level in templates"""
    flash(request, message, category=level)
