from typing import Any, Dict


class InventoryFastAPIApp:
    """
    Duck-typed FastAPI application providing OpenAPI 3.1 schema.
    Compatible with FastApiDriver without requiring fastapi dependency.
    """

    def openapi(self) -> Dict[str, Any]:
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "Inventory Management API",
                "version": "1.0.0",
                "description": "FastAPI service for managing warehouse inventory",
            },
            "paths": {
                "/products": {
                    "get": {
                        "summary": "List inventory products",
                        "description": "Returns all currently available products in stock",
                        "responses": {
                            "200": {
                                "description": "Successful products list",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "summary": "Register new product",
                        "description": "Creates a product entry in the inventory catalogue",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "sku": {"type": "string"},
                                            "quantity": {"type": "integer"},
                                        },
                                        "required": ["sku", "quantity"],
                                    }
                                }
                            }
                        },
                        "responses": {
                            "201": {"description": "Product registered successfully"}
                        },
                    },
                },
                "/products/{sku}": {
                    "get": {
                        "summary": "Get product details",
                        "parameters": [
                            {
                                "name": "sku",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "200": {"description": "Product details"}
                        },
                    }
                },
            },
        }


app = InventoryFastAPIApp()
