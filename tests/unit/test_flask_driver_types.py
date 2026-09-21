# pyright: reportPrivateUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownVariableType=false
from pydantic import BaseModel
from typing import List, Dict
from tera.drivers.flask_driver import FlaskAppDriver

class SampleModel(BaseModel):
    id: int
    name: str
    is_active: bool
    score: float
    tags: List[str]
    metadata: Dict[str, str]

def test_extract_pydantic_fields_types() -> None:
    driver = FlaskAppDriver("dummy:app")
    fields = driver._extract_pydantic_fields(SampleModel)
    field_map = {f.name: f for f in fields}

    assert field_map["id"].type == "integer"
    assert field_map["id"].example == 0

    assert field_map["name"].type == "string"
    assert field_map["name"].example == "string"

    assert field_map["is_active"].type == "boolean"
    assert field_map["is_active"].example is True

    assert field_map["score"].type == "number"
    assert field_map["score"].example == 0.0

    assert field_map["tags"].type == "array"
    assert field_map["tags"].example == []

    assert field_map["metadata"].type == "object"
    assert field_map["metadata"].example == {}

def test_map_type_hint_to_field_type() -> None:
    driver = FlaskAppDriver("dummy:app")

    assert driver._map_type_hint_to_field_type(int) == "integer"
    assert driver._map_type_hint_to_field_type(float) == "number"
    assert driver._map_type_hint_to_field_type(bool) == "boolean"
    assert driver._map_type_hint_to_field_type(list) == "array"
    assert driver._map_type_hint_to_field_type(dict) == "object"
    assert driver._map_type_hint_to_field_type(str) == "string"


def test_flask_driver_extract_converters_and_route_types() -> None:
    import flask

    app = flask.Flask("test_converter_app")

    @app.route("/users/<int:user_id>", methods=["GET"])
    def get_user_untyped(user_id):
        """Get user without type annotations"""
        return "ok"

    @app.route("/items/<float:ratio>/<slug>", methods=["GET"])
    def get_item_mixed(ratio, slug):
        """Get item with float converter and default slug"""
        return "ok"

    @app.route("/orders/<int:order_id>", methods=["POST"])
    def get_order_kwargs(**kwargs):
        """Get order with kwargs"""
        return "ok"

    driver = FlaskAppDriver("dummy:app")

    # Test converter extraction
    converters = driver._extract_flask_converters("/users/<int:user_id>/<float:ratio>")
    assert converters == {"user_id": "int", "ratio": "float"}

    # Test path resolution with rule
    rules = {r.endpoint: r for r in app.url_map.iter_rules() if r.endpoint != "static"}

    ep_user = driver._process_rule(app, rules["get_user_untyped"], "GET")
    assert ep_user.path == "/users/{user_id}"
    assert ep_user.params is not None
    assert len(ep_user.params.path) == 1
    assert ep_user.params.path[0].name == "user_id"
    assert ep_user.params.path[0].type == "integer"
    assert ep_user.params.path[0].example == 0
    assert ep_user.params.path[0].required is True

    ep_item = driver._process_rule(app, rules["get_item_mixed"], "GET")
    assert ep_item.path == "/items/{ratio}/{slug}"
    assert ep_item.params is not None
    assert len(ep_item.params.path) == 2
    assert ep_item.params.path[0].name == "ratio"
    assert ep_item.params.path[0].type == "number"
    assert ep_item.params.path[0].example == 0.0
    assert ep_item.params.path[1].name == "slug"
    assert ep_item.params.path[1].type == "string"
    assert ep_item.params.path[1].example == "string"

    ep_order = driver._process_rule(app, rules["get_order_kwargs"], "POST")
    assert ep_order.path == "/orders/{order_id}"
    assert ep_order.params is not None
    assert len(ep_order.params.path) == 1
    assert ep_order.params.path[0].name == "order_id"
    assert ep_order.params.path[0].type == "integer"
    assert ep_order.params.path[0].example == 0


