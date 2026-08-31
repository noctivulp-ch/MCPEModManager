# 0011 — Las carpetas se nombran legibles, no como las nombra el juego

**Fecha:** 2026-08-30
**Estado:** Aceptada

## Contexto

Al importar un pack desde el juego, la carpeta que queda lleva el nombre del pack
recortado a diez caracteres, con sufijo `(N)` si choca con otra:

```
resource_packs/HideArmorV        ← "§fHide §bArmor§6 | §aV1.2§r"
resource_packs/BetterFoli(1)     ← "Better Foliage Addon RP"
```

La primera idea fue replicar ese recorte, para que instalar con el gestor y con
el juego dieran el mismo resultado y no quedara el pack duplicado.

Al comprobarlo aparecieron dos cosas. La primera: **el patrón encaja en 25 de las
30 carpetas de una instalación real, pero no está demostrado**. El binario del
juego está sin símbolos y no se pudo confirmar la regla en el código; todo lo
instalado allí entró en dos tandas, así que la evidencia es correlacional.

La segunda deja la primera sin importancia: **el juego no usa el nombre de la
carpeta para nada.** Localiza los packs por uuid, como se ve en
`global_resource_pack_settings.json` (ver [0009](0009-identidad-por-uuid.md)).

## Decisión

La carpeta se nombra con el nombre real del pack, limpio de códigos de color
`§x`, sin los caracteres que un sistema de archivos no admite y recortado a 64
caracteres. `Hide Armor | V1.2` da la carpeta `Hide Armor V1.2`.

Los duplicados **no** se evitan por el nombre sino por el uuid: al instalar se
busca ese uuid entre lo que ya hay y, si aparece, se reutiliza su carpeta tal
como estaba. Un pack que importó el juego como `HideArmorV` se actualiza dentro
de `HideArmorV`, sin renombrar ni duplicar nada.

## Consecuencias

En una instalación con historia conviven nombres legibles con recortes anteriores
del juego. Es cosmético: el juego no distingue, y en la lista del gestor se ve el
nombre completo del manifiesto en cualquier caso.

Replicar el recorte habría sido copiar una regla no verificada, con el riesgo de
copiarla mal. Emparejar por uuid resuelve el mismo problema sin depender de ella.
