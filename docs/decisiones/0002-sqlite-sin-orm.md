# 0002 — SQLite directo sin ORM

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

Se necesita persistencia para mods instalados, historial de acciones y registro de archivos ya vistos (badge NEW).

## Decisión

SQLite de la stdlib de Python (`sqlite3`), sin ORM. Tres tablas: `mods`, `historial`, `vistos`.

## Alternativas descartadas

- **SQLAlchemy**: overhead innecesario para tres tablas simples. La app no necesita portabilidad de motor.
- **TinyDB / JSON**: no da las garantías de integridad que necesita el historial de cambios.

## Consecuencias

El schema está en `Store._ESQUEMA` como string SQL. Migraciones futuras son responsabilidad de quien las añada: no hay sistema de migraciones automático. Si se modifica el schema, hay que agregar lógica de migración explícita en `Store.__init__`.
