from app.shared.pagination import PaginationParams
from app.shared.types import UUIDType


def test_pagination_params_defaults_are_defined():
    params = PaginationParams()

    assert params.page == 1
    assert params.page_size == 20


def test_uuid_type_alias_points_to_uuid_class():
    assert UUIDType.__name__ == "UUID"
