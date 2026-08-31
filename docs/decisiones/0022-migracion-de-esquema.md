# 0022 — Las columnas nuevas se añaden a las bases que ya existen

**Fecha:** 2026-08-31
**Estado:** Aceptada

## Contexto

La pestaña de actualizaciones devolvía **cero resultados** en una instalación
real, mientras que la misma comprobación desde una consola encontraba 42 de 59.
La red funcionaba, los packs se leían y la búsqueda daba candidatos.

El error, cuando se consiguió ver, era este:

```
OperationalError: table emparejamientos has no column named uuid_remoto
```

La tabla se había creado con una versión anterior del gestor, antes de que
existiera esa columna. `CREATE TABLE IF NOT EXISTS` **no toca una tabla que ya
está**, así que la columna nunca se añadió. Y el fallo no aparecía al abrir la
base sino al escribir en ella, en mitad de una comprobación, muy lejos de su
causa.

Por qué no se vio antes: los tests crean la base desde cero, y ahí el esquema
siempre está completo. El caso que fallaba —una base de la versión anterior—
solo existía en la máquina de quien venía usando la app.

## Decisión

Al abrir la base se comparan las columnas de cada tabla con las que el esquema ha
ido ganando, y se añaden las que falten:

```python
_COLUMNAS_NUEVAS = {
    "emparejamientos": {"confianza": "TEXT", "uuid_remoto": "TEXT"},
}
```

Explícito y no derivado del `CREATE TABLE`: la lista dice qué se añadió después,
que es justo la información que hace falta y que un esquema no guarda.

Hay un test que crea una base con el esquema anterior, la abre y comprueba que se
puede escribir y que lo que había sigue estando.

## Lo que lo hizo invisible

El barrido captura las excepciones de cada pack para que uno roto no pare los
otros cincuenta. Ese `except` se tragaba el error entero: el resultado era
«cero encontrados», sin ningún mensaje.

Ahora los fallos se cuentan y se devuelven en el mensaje de fin, así que un
problema como este aparece en la propia pestaña en vez de disfrazarse de lista
vacía. **Un `except` amplio necesita una salida por donde se vea lo que atrapó.**

## Y cómo se diagnostica ahora

`mcpemod --diagnostico` imprime instalaciones, contenido, emparejamientos
guardados y el estado de la red; con `--comprobar` hace además un barrido corto
con la misma maquinaria de la pestaña, y el primero sin hilos ni pool para que un
fallo se vea entero.

Existe porque el fallo solo se daba **en el ejecutable y con la base real**, y
desde dentro de la app se manifestaba como una lista vacía. Los caminos que no
tienen forma de contar lo que les pasa se diagnostican adivinando.
