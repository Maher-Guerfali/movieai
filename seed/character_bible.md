# SEED CHARACTER BIBLE

Derived from the Director's uploaded character reference sheets + the story.
The Art Director should treat these as the canonical look; generate variants
(costume/emotion/timeline) from them and keep them consistent across shots.
Style throughout: *Waltz with Bashir* — inked, cross-hatched, muted
sepia/olive palette, high contrast, graphic-novel realism.

---

## MAJOR P

- **Age / period:** 35 in **2010**, Kunduz, Afghanistan (younger timeline).
  A second, **ruined** look exists for 2025/present (see variants).
- **Reference sheet (2010):** front portrait + three study angles (left
  profile, three-quarter, head lowered).
- **Face / build:** strong square jaw, short dark spiky cropped hair, light
  stubble, heavy brow often furrowed, tired but sharp eyes, athletic build.
- **Wardrobe (2010):** dark olive military collared field shirt, dog-tag
  chain at the neck, dark undershirt.
- **Expression register:** controlled, guarded, weary authority; rare warmth
  on the rooftop scenes.
- **Palette:** olive/sepia/khaki, warm shadow, inked hatching.

**Variants to generate:**
- `P_2010_neutral`, `P_2010_3q`, `P_2010_profile`, `P_2010_lookdown`
  (from the sheet).
- `P_2010_rooftop_warm` (softer, night, lamplight).
- `P_2025_ruined` — older, heavy-set, gray, sallow/bloated face, stained
  shirt, empty gaze. Must read as the **same man** wrecked by time and guilt.

---

## LIEUTENANT LM — "Lili Marleen"

- **Period:** 2010 onward; later **Captain**. Aristocratic-elegant yet
  rebellious idealist; came to build schools for girls.
- **Reference sheet:** night portrait in the Afghan camp — watchtower, camp
  lamps, tents behind her.
- **Face / build:** young woman, warm brown eyes, expressive brows,
  freckled/textured skin (rendered in fine cross-hatch), hair pulled up in a
  **bun with loose escaping strands**.
- **Wardrobe (2010):** dark field uniform, **rank insignia** on the shoulder
  boards (pips/stars), collar open over a tee.
- **Expression register:** curious, determined, defiant; later hollowed and
  haunted.
- **Palette:** gold/sepia highlights on skin against deep blue-black night;
  engraving/etched line quality.

**Variants to generate:**
- `LM_2010_camp_night` (from the sheet), `LM_2010_neutral`,
  `LM_2010_3q`, `LM_2010_profile`.
- `LM_teaching` (daylight, at the new school, beaming).
- `LM_captain_decorated` (later uniform, medal she declines).
- `LM_unraveling` (present, gaunt, haunted — ward/Germany).

---

## Consistency rules for the Critic

- P and LM must be recognizably the same person across every variant; the
  Critic scores `character_consistency` against the approved neutral sheet.
- Maintain the **two-timeline distinction** for P (sharp 2010 vs ruined
  2025) without losing identity.
- Hold the style bible (Waltz with Bashir) on every image; reject glossy,
  3D, or photoreal-clean results that break the inked/hatched look.

> Note: the Director provided the two reference sheets in chat. Save the
> actual image files into `seed/refs/` (e.g. `seed/refs/major_p_sheet.png`,
> `seed/refs/lili_marleen_sheet.png`) so the pipeline can use them as
> image-to-image / IP-Adapter / LoRA seeds.
