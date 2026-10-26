"""Prepare explicit local or existing-Cognito staff settings without printing secrets."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import tempfile
from pathlib import Path

import bcrypt
from dotenv import dotenv_values, set_key


def prepare(
    target: Path, mode: str, origin: str, *, source: Path | None = None,
    username: str = "local-author", aws_profile: str = "", apply: bool = False,
    generate_password: bool = False, credentials_only: bool = False,
) -> list[str]:
    from urllib.parse import urlsplit

    url = urlsplit(origin)
    _ = url.port
    if (url.scheme not in ("http", "https") or not url.hostname or url.path or url.query
            or url.fragment or url.username or url.password or any(c.isspace() for c in origin)):
        raise ValueError("Supply an exact origin without a path or credentials.")
    loopback = url.hostname in ("127.0.0.1", "localhost", "::1")
    if mode == "local" and not loopback:
        raise ValueError("Local authentication requires a loopback origin.")
    if not loopback and url.scheme != "https":
        raise ValueError("Non-loopback authentication requires HTTPS.")
    if (generate_password or credentials_only) and mode != "local":
        raise ValueError("Password generation and credentials-only setup apply to local mode only.")
    old = dotenv_values(target, interpolate=False)
    updates = {
        "SOCRATIC_AUTH_MODE": mode,
        "SOCRATIC_ALLOWED_ORIGINS": json.dumps([origin]),
        "SOCRATIC_COOKIE_SECURE": "false" if loopback and url.scheme == "http" else "true",
        "SOCRATIC_SESSION_SECONDS": "900",
    }
    csrf = old.get("SOCRATIC_CSRF_SECRET")
    if csrf and len(csrf) < 32:
        raise ValueError("Existing SOCRATIC_CSRF_SECRET is too short; replace it explicitly.")
    updates["SOCRATIC_CSRF_SECRET"] = csrf or secrets.token_urlsafe(48)
    if mode == "cognito":
        if source is None or source.resolve() == target.resolve():
            raise ValueError("Cognito setup requires a separate explicitly selected source env file.")
        values = dotenv_values(source, interpolate=False)
        for key in ("COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "COGNITO_CLIENT_SECRET"):
            value = values.get(key)
            if not value:
                raise ValueError(f"Source is missing required {key}; no settings changed.")
            updates[key] = value
        pool_region = updates["COGNITO_USER_POOL_ID"].split("_", 1)[0]
        updates["COGNITO_REGION"] = values.get("COGNITO_REGION") or pool_region
        updates["COGNITO_ADMIN_GROUP"] = values.get("COGNITO_ADMIN_GROUP") or "Admins"
        updates["SOCRATIC_AWS_PROFILE"] = aws_profile
    elif mode == "local":
        if not username.strip() or username != username.strip():
            raise ValueError("A nonblank local username without surrounding whitespace is required.")
        updates["SOCRATIC_LOCAL_USERNAME"] = username
        updates["SOCRATIC_LOCAL_CAPABILITIES"] = json.dumps(["author"])
        password_hash = old.get("SOCRATIC_LOCAL_PASSWORD_HASH")
        if generate_password:
            # Explicit rotation. The plaintext is kept only in this gitignored, 0600 .env so the
            # operator can read it; the server verifies against the bcrypt hash alone.
            updates["SOCRATIC_LOCAL_PASSWORD"] = "<generated-on-apply>"
            password_hash = None
            if apply:
                password = secrets.token_urlsafe(18)
                updates["SOCRATIC_LOCAL_PASSWORD"] = password
                password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        elif not password_hash and apply:
            password = getpass.getpass("Local Studio password (12–72 UTF-8 bytes): ")
            confirmation = getpass.getpass("Confirm local password: ")
            if password != confirmation or not 12 <= len(password.encode()) <= 72:
                raise ValueError("Passwords must match and be 12–72 UTF-8 bytes; no settings changed.")
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        if password_hash:
            try:
                bcrypt.checkpw(b"configuration-check", password_hash.encode())
            except ValueError:
                raise ValueError("Existing local password hash is invalid; no settings changed.") from None
        updates["SOCRATIC_LOCAL_PASSWORD_HASH"] = password_hash or "<prompt-on-apply>"
    else:
        raise ValueError("Unknown authentication mode.")
    if credentials_only:
        # Keep the configured auth mode/origins/cookies (e.g. Cognito for full REST); the local
        # launcher forces local mode for its own process only.
        for key in ("SOCRATIC_AUTH_MODE", "SOCRATIC_ALLOWED_ORIGINS", "SOCRATIC_COOKIE_SECURE",
                    "SOCRATIC_SESSION_SECONDS"):
            if old.get(key):
                updates.pop(key)
    if not apply:
        return sorted(updates)
    fd, name = tempfile.mkstemp(prefix=".socratic-auth-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(target.read_text() if target.exists() else "")
        for key, value in updates.items():
            set_key(temporary, key, value, quote_mode="always")
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return sorted(updates)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("local", "cognito"), required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-env", type=Path)
    parser.add_argument("--target-env", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    parser.add_argument("--username", default="local-author")
    parser.add_argument("--aws-profile", default="")
    parser.add_argument("--generate-password", action="store_true",
                        help="Local only: generate/rotate a random password without prompting and save it as "
                             "SOCRATIC_LOCAL_PASSWORD (plus its bcrypt hash) in the target .env.")
    parser.add_argument("--credentials-only", action="store_true",
                        help="Local only: keep existing auth mode/origins/cookie settings; write credentials.")
    parser.add_argument("--apply", action="store_true", help="Write private settings; default is dry-run.")
    args = parser.parse_args()
    try:
        keys = prepare(args.target_env, args.mode, args.origin, source=args.source_env,
                       username=args.username, aws_profile=args.aws_profile, apply=args.apply,
                       generate_password=args.generate_password, credentials_only=args.credentials_only)
    except (ValueError, OSError, EOFError) as exc:
        parser.exit(1, f"Setup failed ({type(exc).__name__}); no configuration values printed. "
                    "Check paths, required keys, origin and password constraints.\n")
    print(("Updated" if args.apply else "Dry-run; would update") + " keys: " + ", ".join(keys))
    if args.apply and args.generate_password:
        print(f"Generated password saved as SOCRATIC_LOCAL_PASSWORD in {args.target_env} (not printed).")
    print("Values hidden. No AWS calls, database operations, service restarts or deployments.")


if __name__ == "__main__":
    main()
