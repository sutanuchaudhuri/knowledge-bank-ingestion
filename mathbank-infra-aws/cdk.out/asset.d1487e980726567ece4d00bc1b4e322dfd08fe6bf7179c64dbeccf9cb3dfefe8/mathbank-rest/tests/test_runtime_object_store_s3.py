"""S3 storage acceptance using a fake client only; never external storage or credentials."""
from __future__ import annotations

import shutil
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest

from mathbank_rest import object_store as store


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.error = False
        self.body = None

    def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))
        if self.error:
            raise RuntimeError("sensitive-sdk-credentials")
        assert kwargs["IfNoneMatch"] == "*" and kwargs["ContentLength"] == len(kwargs["Body"])
        assert "ACL" not in kwargs
        key = (kwargs["Bucket"], kwargs["Key"])
        if key in self.objects:
            raise RuntimeError("PreconditionFailed")
        self.objects[key] = kwargs

    def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        if self.error:
            raise RuntimeError("sensitive-sdk-credentials")
        item = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        self.body = BytesIO(item["Body"])
        return {"Body": self.body, "ContentLength": item["ContentLength"], "Metadata": item["Metadata"]}

    def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))
        if self.error:
            raise RuntimeError("sensitive-sdk-credentials")
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    config = {
        "MATHBANK_OBJECT_BACKEND": "s3", "AWS_ENDPOINT_URL_S3": "https://storage.example.test",
        "MATHBANK_OBJECT_BUCKET": "mathbank-runtime", "AWS_ACCESS_KEY_ID": "fake-access",
        "AWS_SECRET_ACCESS_KEY": "fake-secret", "AWS_REGION": "us-east-1",
        "AWS_SESSION_TOKEN": "", "MATHBANK_OBJECT_ROOT": "",
        "AWS_BUCKET_NAME": "",
    }
    monkeypatch.setattr(store, "_config", lambda: dict(config))
    monkeypatch.setattr(store, "_s3_client", lambda cfg: fake)
    return fake, config


def test_s3_private_atomic_roundtrip_metadata_and_idempotent_delete(s3):
    fake, _ = s3
    item = store.put_bytes(b"private evidence", "svg")
    assert set(item) == {"object_key", "sha256", "size_bytes"}
    assert store.read_bytes(item["object_key"]) == b"private evidence"
    assert fake.body.closed
    assert fake.calls[0][1]["Metadata"] == {"sha256": item["sha256"]}
    assert all("ACL" not in kwargs for _, kwargs in fake.calls)
    store.delete_object(item["object_key"])
    store.delete_object(item["object_key"])
    assert not fake.objects


@pytest.mark.parametrize("suffix", [".wav", ".webm", ".m4a", ".png", ".json", ".txt"])
def test_parent_media_suffixes_supported_without_content_type_assumptions(s3, suffix):
    item = store.put_bytes(b"synthetic private bytes", suffix)
    assert store.read_bytes(item["object_key"]) == b"synthetic private bytes"
    assert item["object_key"].endswith(suffix)
    store.delete_object(item["object_key"])


def test_s3_conditional_creation_refuses_collision(s3, monkeypatch):
    _fake, _ = s3
    fixed = uuid4()
    monkeypatch.setattr(store, "uuid4", lambda: fixed)
    item = store.put_bytes(b"original", "bin")
    with pytest.raises(store.ObjectStoreError, match="write failed"):
        store.put_bytes(b"replacement", "bin")
    assert store.read_bytes(item["object_key"]) == b"original"


@pytest.mark.parametrize("field", [
    "AWS_ENDPOINT_URL_S3", "MATHBANK_OBJECT_BUCKET", "AWS_REGION",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
])
def test_missing_s3_configuration_is_explicit_without_filesystem_fallback(s3, field, monkeypatch):
    fake, config = s3
    config[field] = ""
    monkeypatch.setattr(store, "_root", lambda: pytest.fail("silent filesystem fallback"))
    with pytest.raises(store.ObjectStoreError, match=field):
        store.put_bytes(b"x", "bin")
    assert not fake.calls


@pytest.mark.parametrize("endpoint", [
    "https://user:secret@host.example", "https://host.example?token=secret",
    "http://host.example", "file:///etc/passwd", "not-an-endpoint",
])
def test_s3_endpoint_rejects_credentials_in_url_and_non_https(s3, endpoint):
    _, config = s3
    config["AWS_ENDPOINT_URL_S3"] = endpoint
    with pytest.raises(store.ObjectStoreError, match="credential-free HTTPS") as exc:
        store.put_bytes(b"x", "bin")
    assert endpoint not in str(exc.value)


@pytest.mark.parametrize("mutation", [
    lambda item: item.update(Body=b"changed"),
    lambda item: item.update(ContentLength=store.MAX_OBJECT_BYTES + 1),
    lambda item: item.update(ContentLength=0),
    lambda item: item.update(Metadata={}),
    lambda item: item.update(ContentLength=1),
])
def test_s3_read_bounds_and_integrity_close_response_body(s3, mutation):
    fake, _ = s3
    item = store.put_bytes(b"original", "bin")
    mutation(next(iter(fake.objects.values())))
    with pytest.raises(store.ObjectStoreError, match="integrity check failed"):
        store.read_bytes(item["object_key"])
    assert fake.body.closed


@pytest.mark.parametrize("operation", ["put", "read", "delete"])
def test_s3_sdk_errors_never_expose_credentials(s3, operation):
    fake, _ = s3
    item = store.put_bytes(b"original", "bin")
    fake.error = True
    with pytest.raises(store.ObjectStoreError) as exc:
        if operation == "put":
            store.put_bytes(b"x", "bin")
        elif operation == "read":
            store.read_bytes(item["object_key"])
        else:
            store.delete_object(item["object_key"])
    assert "sensitive-sdk-credentials" not in str(exc.value)


def test_only_root_env_storage_names_are_loaded_and_environment_overrides(monkeypatch):
    root = Path(__file__).parent / f".s3-config-{uuid4().hex}"
    root.mkdir()
    try:
        (root / ".env").write_text(
            "MATHBANK_OBJECT_BUCKET=file-bucket\nAWS_ACCESS_KEY_ID=fake-file-access\n"
            "NEON_AI_GATEWAY_TOKEN=not-storage\nNEON_AUTH_URL=https://auth.example.test\n"
            "AWS_SECRET_ACCESS_KEY='${NEON_AI_GATEWAY_TOKEN}'\n"
        )
        monkeypatch.setattr(store, "REPOSITORY_ROOT", root)
        for name in store._CONFIG_NAMES:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("MATHBANK_OBJECT_BUCKET", "process-bucket")
        config = store._config()
        assert config["MATHBANK_OBJECT_BUCKET"] == "process-bucket"
        assert config["AWS_ACCESS_KEY_ID"] == "fake-file-access"
        assert config["AWS_SECRET_ACCESS_KEY"] == "${NEON_AI_GATEWAY_TOKEN}"
        assert "NEON_AI_GATEWAY_TOKEN" not in config
        assert config["AWS_ENDPOINT_URL_S3"] == ""
        assert store._backend(config) == "s3"
        with pytest.raises(store.ObjectStoreError, match="AWS_ENDPOINT_URL_S3"):
            store.put_bytes(b"x", "bin")
    finally:
        shutil.rmtree(root)


def test_unspecified_bucket_defaults_to_private_runtime_bucket(monkeypatch):
    monkeypatch.setattr(store, "dotenv_values", lambda *args, **kwargs: {})
    for name in store._CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    assert store._config()["MATHBANK_OBJECT_BUCKET"] == "mathbank-runtime"
    monkeypatch.setenv("AWS_BUCKET_NAME", "private-alias-bucket")
    assert store._config()["MATHBANK_OBJECT_BUCKET"] == "private-alias-bucket"
    monkeypatch.setenv("MATHBANK_OBJECT_BUCKET", "private-other-bucket")
    with pytest.raises(store.ObjectStoreError, match="conflict"):
        store._config()
    monkeypatch.setenv("MATHBANK_OBJECT_BUCKET", "")
    assert store._config()["MATHBANK_OBJECT_BUCKET"] == ""


def test_invalid_backend_never_falls_back(s3):
    _, config = s3
    config["MATHBANK_OBJECT_BACKEND"] = "auto"
    with pytest.raises(store.ObjectStoreError, match="must be s3 or filesystem"):
        store.put_bytes(b"x", "bin")


def test_sdk_factory_uses_explicit_storage_credentials_and_sigv4(monkeypatch):
    config = {name: "" for name in store._CONFIG_NAMES}
    config.update({
        "AWS_ENDPOINT_URL_S3": "https://storage.example.test",
        "MATHBANK_OBJECT_BUCKET": "mathbank-runtime",
        "AWS_ACCESS_KEY_ID": "fake-access",
        "AWS_SECRET_ACCESS_KEY": "fake-secret",
        "AWS_SESSION_TOKEN": "fake-session",
        "AWS_REGION": "us-east-1",
    })
    captured = {}
    boto3 = ModuleType("boto3")
    botocore = ModuleType("botocore")
    botocore_config = ModuleType("botocore.config")

    def sdk_config(**kwargs):
        captured["config"] = kwargs
        return kwargs

    def client(service, **kwargs):
        captured["service"], captured["client"] = service, kwargs
        return "fake-client"

    boto3.client = client
    botocore_config.Config = sdk_config
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config)
    assert store._s3_client(config) == "fake-client"
    assert captured["service"] == "s3"
    assert captured["client"]["endpoint_url"] == config["AWS_ENDPOINT_URL_S3"]
    assert captured["client"]["aws_access_key_id"] == "fake-access"
    assert captured["client"]["aws_secret_access_key"] == "fake-secret"
    assert captured["client"]["aws_session_token"] == "fake-session"
    assert captured["client"]["region_name"] == "us-east-1"
    assert captured["config"]["signature_version"] == "s3v4"
    assert captured["config"]["s3"] == {"addressing_style": "path"}


def test_real_sdk_shapes_validate_with_botocore_stub_without_network(s3, monkeypatch):
    from botocore.stub import Stubber

    _, config = s3
    # Restore the actual SDK factory; explicit fake credentials avoid metadata credential discovery.
    monkeypatch.undo()
    client = store._s3_client(config)
    fixed = uuid4()
    key = fixed.hex + ".bin"
    body = b"private bytes"
    import hashlib

    digest = hashlib.sha256(body).hexdigest()
    stubber = Stubber(client)
    stubber.add_response("put_object", {}, {
        "Bucket": "mathbank-runtime", "Key": key, "Body": body, "ContentLength": len(body),
        "ContentType": "application/octet-stream", "Metadata": {"sha256": digest}, "IfNoneMatch": "*",
    })
    stubber.add_response("get_object", {
        "Body": BytesIO(body), "ContentLength": len(body), "Metadata": {"sha256": digest},
    }, {"Bucket": "mathbank-runtime", "Key": key})
    stubber.add_response("delete_object", {}, {"Bucket": "mathbank-runtime", "Key": key})
    monkeypatch.setattr(store, "_config", lambda: dict(config))
    monkeypatch.setattr(store, "_s3_client", lambda cfg: client)
    monkeypatch.setattr(store, "uuid4", lambda: fixed)
    with stubber:
        result = store.put_bytes(body, "bin")
        assert result["object_key"] == key
        assert store.read_bytes(key) == body
        store.delete_object(key)
        stubber.assert_no_pending_responses()
