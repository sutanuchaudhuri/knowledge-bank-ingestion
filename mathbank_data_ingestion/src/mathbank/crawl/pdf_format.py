"""PDF signature validation, including whitespace-prefixed legacy documents."""


def has_pdf_header(content: bytes) -> bool:
    return content[:1024].lstrip(b" \t\r\n").startswith(b"%PDF-")
