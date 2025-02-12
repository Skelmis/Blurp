import secrets


def get_csp() -> tuple[str, str]:
    nonce = secrets.token_urlsafe(16)
    text = (
        "default-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; script-src 'nonce-{}' "
        "'strict-dynamic'; style-src 'nonce-{}' 'strict-dynamic'; require-trusted-types-for 'script'"
    )
    text = text.format(nonce, nonce)
    return text, nonce
