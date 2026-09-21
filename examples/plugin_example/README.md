# Custom Plugin Example

This directory demonstrates how to extend `tera-cli` with custom drivers and writers without modifying core codebase.

## Structure

* `custom_plugin.py`: Implements `CustomRouteListDriver` and the registration hook `register_tera_plugin`.
* `api.routes`: Plain-text API routes file parsed by the custom driver.
* `tera.toml`: Declares the plugin hook in `[plugins.load]`.

## How It Works

When `tera` runs in this directory, it loads `tera.toml`:

```toml
[plugins]
load = ["custom_plugin:register_tera_plugin"]
```

The `register_tera_plugin(driver_registry, writer_registry)` function registers `CustomRouteListDriver` with an automatic matcher for any `.routes` file.

## Testing

Run from this folder:

```bash
tera scan api.routes -o docs.yaml
```

Inspect the generated canonical IR:

```bash
tera validate docs.yaml
tera lint docs.yaml
```

