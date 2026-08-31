# 0020 — Identidad de un pack: el uuid manda, el nombre rescata

**Fecha:** 2026-08-31
**Estado:** Aceptada — corrige a [0009](0009-identidad-por-uuid.md) y [0011](0011-nombre-de-carpeta-legible.md)

## Contexto

La ADR 0009 fijó que la identidad de un pack es su `header.uuid`, con una prueba
que parecía concluyente: el juego guarda los ajustes de cada pack bajo `pack_id`
en `global_resource_pack_settings.json`, nunca bajo una ruta.

La prueba era buena pero la conclusión no. Ese uuid es la identidad **en
ejecución** — para saber a qué pack pertenecen unos ajustes. No es la identidad
**para actualizar**.

Lo que lo destapó fue un caso real. El pack «Déesse UI Pack» del equipo de prueba
está en la versión 1.3.1 y hay publicadas hasta la 1.3.9. El emparejamiento no lo
encontraba, y al mirar por qué:

```
v1.3.1   header=a0909a90-90aa-9152-1310-157157157157
         module=a1709a90-9a21-9050-1310-157157157157
v1.3.9   header=a0909a90-e0c2-9a52-1390-157157157157
         module=a1709a90-2cc1-9a50-1390-157157157157
                                    ▲▲▲▲  el número de versión, dentro del uuid
```

Este autor **codifica la versión dentro del uuid**, y cambia también el
`modules[].uuid`. Lo único idéntico en las cuatro versiones publicadas es
`header.name`: «Déesse UI Pack».

Y el juego actualiza ese pack sin problema al ejecutar el `.mcpack` nuevo. Con el
uuid cambiado, no puede estar guiándose por él.

## Lo que dice la norma

Antes de seguir deduciendo, se consultó la documentación oficial. Es explícita, y
corrige la conclusión a la que llevaba la ingeniería inversa:

> **`uuid`** — *"This is a special type of identifier that uniquely identifies
> this pack from any other pack."*
>
> **`version`** — *"The version number is used when importing a pack that has been
> imported before. The new pack will replace the old one if the version is
> higher, and ignored if it's the same or lower."*
>
> — [Add-Ons Reference: manifest.json](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/addonsreference/packmanifest)

O sea: **el uuid identifica el pack y debe ser estable entre versiones**; lo que
sube es el número de versión, y eso es lo que dispara el reemplazo al reimportar.

Así que «Déesse UI Pack» no está describiendo cómo funciona el juego: está
**incumpliendo la norma**. Para el juego, cada versión suya es un pack nuevo, y
se le acumulan. Los packs que sí mantienen el uuid —la mayoría— se actualizan
solos, que es lo que se observa en la práctica.

De paso, la documentación aporta algo que no se había considerado: reimportar una
versión **igual o menor se ignora**. El juego no deja revertir; el gestor sí,
porque instala directamente en la carpeta.

## El modelo

1. **El `header.uuid` es la identidad, y se mira primero.** Es la norma.
2. **El `header.name` es el respaldo.** Cubre los packs cuyo autor cambia el uuid,
   donde el gestor puede hacerlo mejor que el juego: reconocerlos y reemplazar en
   vez de acumular.

Sobre el nombrado de carpetas la documentación no dice nada, así que se conserva
lo observado: el juego deriva la carpeta del nombre del pack —quitando los
códigos `§`, las barras verticales y los espacios, y recortando a diez
caracteres—. Comprobado contra las 43 carpetas de la instalación de prueba,
**acierta en 42**. Replicarlo no cuesta nada y mantiene una sola carpeta por pack
se instale por donde se instale.

`BetterFoli`, `BetterFoli(1)` y `BetterFoli(2)` son packs distintos («…NG»,
«…Addon RP», «…FG») cuyos nombres solo chocan **después** del recorte: por eso
llevan sufijo en vez de pisarse.

## Decisión

`mcpemod.core.identidad` concentra las dos ideas:

- `clave_de_pack(nombre)` — la identidad del pack, para comparar.
- `carpeta_del_juego(nombre)` — la regla del juego, para nombrar.

Y de ahí:

1. **El destino de una instalación se busca por uuid y, si no aparece, por nombre.**
   Si ya hay ese pack, se reemplaza su carpeta: eso convierte la instalación en
   una actualización, como haría el juego.
2. **Las carpetas nuevas se nombran como las nombraría el juego.** No es
   cosmético: si el gestor usara otro nombre, el mismo pack acabaría dos veces —
   una por cada vía de instalación.
3. **Al emparejar con un catálogo valen las dos señales**, uuid o nombre. Los
   autores no son consistentes y cada una cubre lo que la otra pierde:

   | Autor | uuid | nombre | Qué lo empareja |
   |---|---|---|---|
   | Déesse UI | cambia cada versión | estable | el nombre |
   | Hide Armor | estable | lleva la versión dentro | el uuid |

   Con una sola señal, la mitad quedaría fuera.
4. **La clave ignora la versión metida en el nombre** («Hide Armor \| V1.2» y
   «Hide Armor \| V1.3.1» son el mismo pack) pero **no** los sufijos que
   distinguen hermanos («NG» / «FG», «RP» / «BP»), que sí son packs distintos y
   conviven instalados.
5. **El uuid publicado sigue sirviendo**: si es el mismo que el instalado, es
   exactamente la misma versión, por más que el número diga otra cosa.

## La lección

Se llegó hasta aquí por ingeniería inversa —manifiestos, carpetas, timestamps—
teniendo la documentación oficial a un buscador de distancia. La conclusión a la
que llevaba era plausible, encajaba con todo lo observado, y era incorrecta en su
premisa central. **Consultar la fuente antes de deducir el comportamiento de un
sistema documentado.**

## Consecuencias

Dos packs realmente distintos con el mismo nombre se tratarían como el mismo. En
la instalación de prueba pasaría con los cuatro cuyo `header.name` es la clave sin
traducir `pack.name` — pero el gestor la resuelve desde `texts/*.lang`, que es
justo lo que el juego no hace, así que ahí es más preciso que él.

El nombrado a diez caracteres es feo de leer en el explorador de archivos. Es el
precio de que el juego reconozca lo que instala el gestor, y al revés. La lista
del gestor muestra el nombre completo del manifiesto en todo caso.

La regla de nombrado falla en un caso de los 43 —un pack llamado literalmente
`pack.name` que colisionaba y quedó en `pack(1)` en vez de `pack.name(1)`—. Es un
nombre ya anómalo de por sí; queda anotado como límite conocido.
