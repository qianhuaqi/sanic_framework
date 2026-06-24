from framework.extensions.auth import token_required
from framework.extensions.maintenance import maintenance_required
from framework.extensions.signing import signing_required


def test_security_extension_decorators_are_callable():
    assert callable(token_required)
    assert callable(signing_required)
    assert callable(maintenance_required)
