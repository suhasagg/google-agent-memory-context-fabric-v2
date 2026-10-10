import pytest
from app.sharing import validate_share
def test_no_working_share():
 with pytest.raises(ValueError):validate_share("a","b",["working"],{})
