"""
Reclasifica el campo "tipo" de cada libro en el catálogo HTML, aplicando
reglas de fusión de categorías + overrides puntuales + heurísticas para
"Sin especificar".

Uso:
    python reclasificar_tipos.py

Ajustá HTML_IN / HTML_OUT abajo. El script:
  1. Lee el JSON embebido en el HTML (bloque <script id="book-data">)
  2. Aplica las reglas de clasificación
  3. Imprime un log de todos los cambios + la distribución final
  4. Escribe un HTML nuevo con los datos actualizados (no pisa el original)
"""

import json
import re

# ---------------- CONFIG ----------------
HTML_IN = "Catalogo_Manuales.html"
HTML_OUT = "Catalogo_Manuales_actualizado.html"
# -----------------------------------------

CAMPANA = "Campaña / Aventura"
HOMEBREW = "Homebrew / Fanmade"
PLAYTEST = "Playtest (Unearthed Arcana)"
OFICIAL = "Oficial"
TERCEROS = "Contenido de terceros"

# Overrides explícitos por substring del NOMBRE (case-insensitive).
# Máxima prioridad: se evalúan antes que cualquier otra regla.
# Agregá acá casos puntuales que la heurística general clasificaría mal.
OVERRIDES = [
    ("dark archive", OFICIAL),
    ("howl of the wild", OFICIAL),
    ("puerta de baldur - descenso a averno", OFICIAL),
    ("tomo de enemigos de mordenkainen", OFICIAL),
    ("battlezoo ancestries", TERCEROS),
    ("unearthed arcana 2021 (feywild)", PLAYTEST),
    ("unearthed arcana, viajeros del multiverso", PLAYTEST),
    ("honor entre ladrones", HOMEBREW),
    ("partidas subidas de tono", HOMEBREW),
    ("guía del dungeon master + equipo de aventurero", OFICIAL),
]

# Listas para resolver "Sin especificar" por nombre (agregá más según
# vayas encontrando libros nuevos sin clasificar).
CAMPANA_NAMES = [
    "dungeons and hyrule", "multiverso conocido",
]

HOMEBREW_NAMES = [
    "compendio de conjuros", "compendio de laserllama", "laserllama",
    "el mimi aquelarre de oni no pipo", "el niila bar de oni no pipo",
    "el lily laboratorio de oni no pipo", "la tienda de oni no pipo",
    "la wuxia de oni no pipo", "la ciudadela: el nuevo mundo",
    "el caldero de tasha para todo", "the last god", "guía de heliana",
    "polyhedrooze", "the shining shrine", "códices del gremio",
    "compendium de arcana y lore de lesda", "colegio del barbárdico",
    "anton y el multiverso de multiversos", "condiciones complementarias",
    "dones de pacto extendidos", "umamusume", "recorrido por el bosque",
    "guía de viajes de kalapop", "compilatorio aberrante de los infernales",
    "guia de ascendencias", "cazador de sangre", "compendium planos de nosrol",
    "tomo de las bestias", "edición mejorada", "bestiario 1",
    "códices de artass", "codices de artass",
]


def classify(book):
    nombre_l = book["nombre"].lower()
    tipo = book["tipo"]

    # 1. overrides explícitos ganan siempre
    for kw, categoria in OVERRIDES:
        if kw in nombre_l:
            return categoria

    # 2. reglas generales por tipo ya existente
    #    prioridad: Oficial > Playtest > Terceros > Campaña > Homebrew
    tipo_l = tipo.lower()
    if tipo in (OFICIAL, "Oficial + Fanmade"):
        return tipo  # no tocar
    if "playtest" in tipo_l or "unearthed arcana" in tipo_l:
        return PLAYTEST
    if tipo == TERCEROS:
        return TERCEROS
    if "campaña" in tipo_l or "stranger things" in tipo_l or "industrial-corrompido" in tipo_l:
        return CAMPANA
    if tipo in ("Homebrew", "Fanmade"):
        return HOMEBREW

    # 3. "Sin especificar": listas explícitas por nombre
    if tipo == "Sin especificar":
        for kw in CAMPANA_NAMES:
            if kw in nombre_l:
                return CAMPANA
        for kw in HOMEBREW_NAMES:
            if kw in nombre_l:
                return HOMEBREW
        return tipo  # sigue sin especificar si no matcheó nada

    return tipo  # cualquier otro caso no contemplado, no tocar


def main():
    with open(HTML_IN, "r", encoding="utf-8") as f:
        html = f.read()

    books_json = html.split('<script id="book-data" type="application/json">')[1].split("</script>")[0].strip()
    books = json.loads(books_json)

    changes = []
    for book in books:
        old = book["tipo"]
        new = classify(book)
        if new != old:
            changes.append((book["nombre"], old, new))
            book["tipo"] = new

    print(f"Total cambios aplicados: {len(changes)}")
    for nombre, old, new in changes:
        print(f"  {nombre[:55]:55s} | {old!r:35s} -> {new!r}")

    from collections import Counter
    print("\nDistribución final de tipos:")
    for tipo, count in Counter(b["tipo"] for b in books).most_common():
        print(f"  {count:4d}  {tipo}")

    sin_esp = [b["nombre"] for b in books if b["tipo"] == "Sin especificar"]
    if sin_esp:
        print(f"\n⚠️  Quedan {len(sin_esp)} libros sin clasificar. Agregalos a CAMPANA_NAMES u HOMEBREW_NAMES:")
        for n in sin_esp:
            print("   -", n)

    # --- reinyectar en el HTML (book-data + tipo-data) ---
    new_books_json = json.dumps(books, ensure_ascii=False)
    tipos_list = sorted(set(b["tipo"] for b in books if b["tipo"]))
    new_tipos_json = json.dumps(tipos_list, ensure_ascii=False)

    pattern_books = re.compile(
        r'(<script id="book-data" type="application/json">\n?)(.*?)(\n?</script>)', re.DOTALL
    )
    html, n1 = pattern_books.subn(lambda m: m.group(1) + new_books_json + m.group(3), html, count=1)

    pattern_tipos = re.compile(
        r'(<script id="tipo-data" type="application/json">\n?)(.*?)(\n?</script>)', re.DOTALL
    )
    html, n2 = pattern_tipos.subn(lambda m: m.group(1) + new_tipos_json + m.group(3), html, count=1)

    if n1 != 1 or n2 != 1:
        print("\n⚠️  No se pudo encontrar/reemplazar uno de los bloques <script> esperados en el HTML.")
        print("   Revisá que HTML_IN tenga los ids 'book-data' y 'tipo-data'.")
        return

    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Listo. Archivo actualizado guardado en: {HTML_OUT}")


if __name__ == "__main__":
    main()
