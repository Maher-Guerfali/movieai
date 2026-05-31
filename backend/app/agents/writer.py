from app.models.entities import AssetKind


SEED_SCENES = [
    ("kunduz-first-meeting", "Kunduz, First Meeting", "Camp courtyard, rooftop nights, schools beginning.", "Afghan Camp"),
    ("the-kiss-threat", "The Kiss and the Threat", "School opening, the relationship, the crucified-girl letter.", "Village School"),
    ("the-transfer", "The Transfer", "P signs the order that saves LM by breaking her heart.", "Afghan Camp"),
    ("clearance-granted", "Clearance Granted", "The truck strike and P's collapse into guilt.", "Desert Road"),
    ("syrian-border", "Reunion at the Syrian Border", "LM finds the ruined P in 2025.", "Syrian Border Center"),
    ("resignation", "Resignation", "LM declines the medal and leaves the military.", "Berlin Office"),
    ("plea-for-punishment", "Petty Crime as a Plea", "Perfume, break-ins, and the toy gun.", "Munich Streets"),
    ("the-ward", "The Ward", "Therapy, forbidden contact, and the final attempt.", "Psychiatric Ward"),
    ("coda", "Coda", "Kabul, Berlin, Munich, and the jasmine letter.", "Munich Apartment"),
]


SEED_ASSETS = [
    (
        AssetKind.ENVIRONMENT,
        "Afghan Camp (Kunduz, 2010)",
        "Dusty fortified camp with tents, watchtower, generators, and rooftop night conversations.",
    ),
    (
        AssetKind.ENVIRONMENT,
        "Munich Apartment (present)",
        "Quiet aged interior where the jasmine-scented letter is opened.",
    ),
    (
        AssetKind.ENVIRONMENT,
        "Syrian Border Center (2025)",
        "Air-traffic-control room with screens, fluorescent fatigue, and desert beyond the glass.",
    ),
    (
        AssetKind.ENVIRONMENT,
        "Psychiatric Ward",
        "Cold institutional ward, overlit corridors, clipped routines, and emotional isolation.",
    ),
    (
        AssetKind.ENVIRONMENT,
        "Desert Road of the Truck Strike",
        "Heat-hazed road, dust, drone distance, and moral aftermath rather than spectacle.",
    ),
    (
        AssetKind.CHARACTER,
        "Major P",
        "Disciplined officer in 2010; ruined, gray, and swollen by guilt in 2025.",
    ),
    (
        AssetKind.CHARACTER,
        "Lieutenant LM (Lili Marleen)",
        "Aristocratic, rebellious idealist who builds schools and later unravels under the war's weight.",
    ),
    (AssetKind.PROP, "Threatening Letter", "A newspaper-hidden symbol of a crucified girl; no words needed."),
    (AssetKind.PROP, "Jasmine-Scented Letter", "The coda letter, intimate and devastating."),
    (AssetKind.PROP, "Cracked Door", "The splinter P touches after LM leaves."),
]


def screenplay_excerpt() -> str:
    return (
        "The screenplay opens in Kunduz with wind carrying dust over a fortified camp. "
        "Major P watches Lieutenant LM cross the courtyard, all new uniform and impossible conviction. "
        "Their bond grows through school-building, rooftop talks, and a love neither can safely name. "
        "When P discovers the Taliban threat against her, he engineers her transfer and accepts being hated. "
        "Three weeks later his clearance order kills five boys beneath a truck, splitting the film into the "
        "sharp 2010 memory and the ruined 2025 aftermath. The final movement follows LM's resignation, "
        "institutional collapse, and the Munich letter that leaves P alone with jasmine and ash."
    )


def brief_for(kind: AssetKind, name: str, description: str) -> str:
    return (
        f"{name} must read in Waltz with Bashir style: rotoscoped-real anatomy, hand-drawn ink, "
        f"muted sepia/olive palette, high-contrast hatching, and restrained war-memory tone. "
        f"Core brief: {description}"
    )
