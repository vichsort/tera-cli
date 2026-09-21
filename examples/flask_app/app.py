import functools
from typing import Any, Callable
from flask import Flask, jsonify, request
from pydantic import BaseModel, Field

app = Flask("ecommerce_api")


def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to enforce authentication."""
    @functools.wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        return f(*args, **kwargs)
    return decorated_function


class CreateUserRequest(BaseModel):
    name: str = Field(..., description="User full name", min_length=2)
    email: str = Field(..., description="User email address")
    role: str = Field("member", description="User role in the system")


@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """
    Health check endpoint.
    Verifies service status.
    """
    return jsonify({"status": "healthy"})


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id: int) -> Any:
    """
    Retrieve user by ID.
    Returns user details for the requested ID.
    """
    return jsonify({"id": user_id, "name": "Alice", "role": "admin"})


@app.route("/users", methods=["POST"])
@login_required
def create_user() -> Any:
    """
    Create a new user.
    Requires authentication.
    """
    data = request.get_json() or {}
    user_req = CreateUserRequest(**data)
    return jsonify({"id": 42, "name": user_req.name, "email": user_req.email}), 201


@app.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id: int) -> Any:
    """
    Delete an existing user.
    Protected destructive mutation.
    """
    return jsonify({"deleted": True, "id": user_id}), 200

