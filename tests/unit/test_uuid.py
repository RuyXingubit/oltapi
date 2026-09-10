import time
import uuid
from app.core.uuid import generate_uuid7, is_valid_uuid7


def test_generate_uuid7_format_and_version():
    uid = generate_uuid7()
    assert isinstance(uid, str)
    assert len(uid) == 36
    assert uid.count("-") == 4

    parsed = uuid.UUID(uid)
    assert parsed.version == 7
    assert parsed.variant == uuid.RFC_4122
    assert is_valid_uuid7(uid) is True


def test_is_valid_uuid7_rejects_invalid_values():
    assert is_valid_uuid7("invalid-uuid-string") is False
    assert is_valid_uuid7("") is False
    assert is_valid_uuid7(None) is False

    # UUIDv4 deve ser rejeitado pela função de validação de UUIDv7
    v4_uid = str(uuid.uuid4())
    assert is_valid_uuid7(v4_uid) is False


def test_uuid7_monotonic_order():
    uids = []
    for _ in range(5):
        uids.append(generate_uuid7())
        time.sleep(0.002)  # 2ms para avançar o timestamp

    # Como são ordenados no tempo, ordenar alfabeticamente deve preservar a ordem de criação
    sorted_uids = sorted(uids)
    assert uids == sorted_uids
