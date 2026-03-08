# Endpoint placement (infoSentry)

- Routers live in `src/modules/<module>/interfaces/routers.py`.
- Request/response schemas live in `src/modules/<module>/interfaces/schemas.py`.
- Route layer only validates input, wires dependencies, and calls application services.
