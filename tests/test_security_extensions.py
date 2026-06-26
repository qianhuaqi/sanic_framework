from lingshu.extensions.auth import token_required
from lingshu.extensions.maintenance import maintenance_required
from lingshu.extensions.signing import signing_required


def test_security_extension_decorators_are_callable():
    assert callable(token_required)
    assert callable(signing_required)
    assert callable(maintenance_required)
