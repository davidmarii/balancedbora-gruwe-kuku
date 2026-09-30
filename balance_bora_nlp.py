# balance_bora_nlp.py
"""
Lightweight rule-based NLP for BalancedBora.

Provides:
  - normalize_feed_name(name) -> canonical SQLite ingredient name (or None)
  - BalanceBoraInterpreter     -> .interpret(text, current_lang) -> dict

No external ML dependencies. Pure Python + regex.
Designed to run in <1ms so it doesn't slow the WhatsApp webhook.
"""

import re
from typing import Optional, List, Dict


# ============================================================
# FEED NAME ALIASES
# Maps farmer-typed words (any language) -> canonical SQLite names.
# Canonical names must match ingredient_name values in the DB exactly.
# ============================================================
FEED_ALIASES: Dict[str, str] = {
    # ---- maize / mahindi ----
    "maize":            "MAIZE GRAIN",
    "maize grain":      "MAIZE GRAIN",
    "corn":             "MAIZE GRAIN",
    "mahindi":          "MAIZE GRAIN",
    "mubî":             "MAIZE GRAIN",
    "mubi":             "MAIZE GRAIN",

    # ---- wheat bran / makapi ya ngano ----
    "wheat bran":       "WHEAT BRAN",
    "wheat pollard":    "WHEAT BRAN",
    "pollard":          "WHEAT BRAN",
    "bran":             "WHEAT BRAN",
    "makapi ya ngano":  "WHEAT BRAN",
    "makapi ma ngano":  "WHEAT BRAN",
    "ngano":            "WHEAT BRAN",

    # ---- rice bran ----
    "rice bran":        "RICE BRAN",
    "makapi ya mchele": "RICE BRAN",
    "makapi ma mchele": "RICE BRAN",
    "mchele":           "RICE BRAN",

    # ---- sorghum ----
    "sorghum":          "SORGHUM",
    "mtama":            "SORGHUM",

    # ---- cassava chips ----
    "cassava":          "CASSAVA CHIPS",
    "cassava chips":    "CASSAVA CHIPS",
    "muhogo":           "CASSAVA CHIPS",
    "manioc":           "CASSAVA CHIPS",

    # ---- soybean meal / cake ----
    "soybean meal":     "SOYBEAN MEAL",
    "soya meal":        "SOYBEAN MEAL",
    "soya":             "SOYBEAN MEAL",
    "soybean":          "SOYBEAN MEAL",
    "mlo wa soya":      "SOYBEAN MEAL",

    # ---- sunflower cake ----
    "sunflower cake":   "SUNFLOWER CAKE",
    "sunflower":        "SUNFLOWER CAKE",
    "alizeti":          "SUNFLOWER CAKE",
    "keki ya alizeti":  "SUNFLOWER CAKE",

    # ---- cottonseed cake ----
    "cottonseed cake":  "COTTONSEED CAKE",
    "cotton seed cake": "COTTONSEED CAKE",
    "cottonseed":       "COTTONSEED CAKE",
    "pamba":            "COTTONSEED CAKE",
    "keki ya pamba":    "COTTONSEED CAKE",

    # ---- fish meal ----
    "fish meal":        "FISH MEAL",
    "fishmeal":         "FISH MEAL",
    "fish":             "FISH MEAL",
    "samaki":           "FISH MEAL",
    "mlo wa samaki":    "FISH MEAL",
    "thamaki":          "FISH MEAL",
    "mlo wa thamaki":   "FISH MEAL",

    # ---- blood meal ----
    "blood meal":       "BLOOD MEAL",
    "blood":            "BLOOD MEAL",
    "damu":             "BLOOD MEAL",
    "mlo wa damu":      "BLOOD MEAL",

    # ---- limestone ----
    "limestone":        "LIMESTONE",
    "lime":             "LIMESTONE",
    "chokaa":           "LIMESTONE",
    "mawe ya chokaa":   "LIMESTONE",

    # ---- dicalcium phosphate ----
    "dicalcium phosphate": "DICALCIUM PHOSPHATE",
    "dcp":              "DICALCIUM PHOSPHATE",
    "phosphate":        "DICALCIUM PHOSPHATE",

    # ---- oyster shell ----
    "oyster shell":     "OYSTER SHELL",
    "oyster":           "OYSTER SHELL",
    "shell":            "OYSTER SHELL",

    # ---- premix ----
    "premix":           "VITAMIN-MINERAL PREMIX",
    "vitamin premix":   "VITAMIN-MINERAL PREMIX",
    "mineral premix":   "VITAMIN-MINERAL PREMIX",
    "vitamin":          "VITAMIN-MINERAL PREMIX",
    "mineral":          "VITAMIN-MINERAL PREMIX",

    # ---- salt ----
    "salt":             "SALT",
    "chumvi":           "SALT",
    "common salt":      "SALT",

    # ---- methionine ----
    "methionine":       "METHIONINE",
    "meth":             "METHIONINE",

    # ---- lysine ----
    "lysine":           "LYSINE",
    "lys":              "LYSINE",

    # ---- sweet potato vines ----
    "sweet potato vines": "SWEET POTATO VINES",
    "sweet potato":     "SWEET POTATO VINES",
    "viazi":            "SWEET POTATO VINES",
    "majani ya viazi":  "SWEET POTATO VINES",
    "vines":            "SWEET POTATO VINES",

    # ---- lucerne / alfalfa ----
    "lucerne":          "LUCERNE HAY",
    "lucerne hay":      "LUCERNE HAY",
    "alfalfa":          "LUCERNE HAY",
    "majani ya lucerne":"LUCERNE HAY",

    # ---- grass hay ----
    "grass hay":        "GRASS HAY",
    "grass":            "GRASS HAY",
    "hay":              "GRASS HAY",
    "nyasi":            "GRASS HAY",
    "majani ya nyasi":  "GRASS HAY",

    # ---- brewers grains ----
    "brewers grains":   "BREWERS GRAINS",
    "brewers":          "BREWERS GRAINS",
    "brewer":           "BREWERS GRAINS",
    "bia":              "BREWERS GRAINS",
    "makapi ya bia":    "BREWERS GRAINS",
    "makapi ma bia":    "BREWERS GRAINS",
}


# ============================================================
# SPECIES / STAGE DETECTION
# ============================================================
SPECIES_ALIASES = {
    "pig":     ["pig", "pigs", "hog", "swine", "nguruwe", "gruwe", "ngurue"],
    "chicken": ["chicken", "chickens", "hen", "hens", "kuku", "nguku",
                "ngûkû", "broiler", "layer"],
}

STAGE_ALIASES = {
    # pigs
    "p1": ["weaner", "weaner pig", "pig weaner", "mtoto wa nguruwe"],
    "p2": ["grower", "grower pig", "pig grower", "mkubwa"],
    "p3": ["finisher", "finisher pig", "pig finisher", "mwisho"],
    "p4": ["gestating sow", "pregnant sow", "gestating",
           "tumbili mjamzito", "mjamzito"],
    "p5": ["lactating sow", "nursing sow", "lactating",
           "tumbili ananyonyesha", "ananyonyesha"],
    # chickens
    "c1": ["broiler starter", "broiler start", "broiler mwanzo"],
    "c2": ["broiler grower", "broiler mkubwa"],
    "c3": ["broiler finisher", "broiler finish", "broiler mwisho"],
    "c4": ["layer starter", "layer start", "layer mwanzo"],
    "c5": ["layer grower", "layer mkubwa"],
    "c6": ["laying hen", "layer", "laying", "mzima", "layer mzima"],
}

# Rough language detector — used only to set a hint, never to translate.
LANG_KEYWORDS = {
    "sw":  ["na", "ninayo", "tafadhali", "ninataka", "nguruwe", "kuku",
            "mahindi", "samaki", "chakula", "naomba", "nina", "sawa"],
    "ki":  ["nîndî", "wî", "mwega", "ngûkû", "mûbî", "rîtheru", "cokeria"],
    "mer": ["ntathimana", "urova", "theru", "ngûkû", "mûbî", "cokeria"],
}


def _norm(text: str) -> str:
    """Lowercase, strip, collapse spaces."""
    return re.sub(r"\s+", " ", str(text).lower().strip())


def normalize_feed_name(name: str) -> Optional[str]:
    """
    Return the canonical SQLite ingredient name for a given farmer input,
    or None if we can't identify it.

    Tries:
      1. Exact alias match
      2. Whole-word containment (e.g. "some maize grain here")
      3. Partial token match as last resort
    """
    if not name:
        return None
    n = _norm(name)

    # 1. exact
    if n in FEED_ALIASES:
        return FEED_ALIASES[n]

    # 2. whole-word substring — longest alias first to prefer specific matches
    for alias in sorted(FEED_ALIASES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", n):
            return FEED_ALIASES[alias]

    # 3. loose fallback — token contains alias, or alias contains token
    tokens = n.split()
    for alias in sorted(FEED_ALIASES.keys(), key=len, reverse=True):
        for tok in tokens:
            if len(tok) >= 4 and (tok in alias or alias in tok):
                return FEED_ALIASES[alias]

    return None


def _detect_species(text: str) -> Optional[str]:
    n = _norm(text)
    for species, kws in SPECIES_ALIASES.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", n):
                return species
    return None


def _detect_stage(text: str) -> Optional[str]:
    n = _norm(text)
    # longest phrase first so "broiler starter" beats "starter"
    for stage, kws in STAGE_ALIASES.items():
        for kw in sorted(kws, key=len, reverse=True):
            if re.search(rf"\b{re.escape(kw)}\b", n):
                return stage
    return None


def _detect_lang(text: str) -> Optional[str]:
    n = _norm(text)
    scores = {"sw": 0, "ki": 0, "mer": 0}
    for lang, kws in LANG_KEYWORDS.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", n):
                scores[lang] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _extract_feeds(text: str) -> List[str]:
    """
    Find every feed mention in text. Returns a list of canonical names.
    Handles both single-word and multi-word aliases.
    """
    n = _norm(text)
    found: List[str] = []
    seen = set()

    # Multi-word aliases first
    for alias in sorted(FEED_ALIASES.keys(), key=lambda a: len(a.split()), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", n):
            canonical = FEED_ALIASES[alias]
            if canonical not in seen:
                found.append(canonical)
                seen.add(canonical)

    return found


# ============================================================
# PUBLIC INTERPRETER CLASS
# ============================================================
class BalanceBoraInterpreter:
    """
    Rule-based interpreter for BalancedBora WhatsApp messages.

    Usage:
        interp = BalanceBoraInterpreter()
        result = interp.interpret("nina mahindi na soya kwa nguruwe grower",
                                  current_lang="sw")
        # -> {
        #      "species": "pig",
        #      "stage":   "p2",
        #      "feeds":   ["MAIZE GRAIN", "SOYBEAN MEAL"],
        #      "lang":    "sw",
        #      "confidence": 0.75,
        #    }
    """

    def interpret(self, text: str, current_lang: str = "en") -> Dict:
        if not text:
            return {
                "species": None, "stage": None, "feeds": [],
                "lang": current_lang, "confidence": 0.0,
            }

        species = _detect_species(text)
        stage = _detect_stage(text)
        feeds = _extract_feeds(text)
        lang = _detect_lang(text) or current_lang

        # Consistency: if stage is pig-stage but species detected as chicken,
        # trust the stage (e.g. user said "broiler" not "chicken").
        if stage and not species:
            species = "pig" if stage.startswith("p") else "chicken"
        if stage and species:
            stage_prefix = "p" if species == "pig" else "c"
            if not stage.startswith(stage_prefix):
                # stage disagrees with species — species wins, drop stage
                stage = None

        # Confidence heuristic: more signals -> higher confidence
        signals = sum([bool(species), bool(stage), len(feeds) > 0])
        confidence = {0: 0.0, 1: 0.4, 2: 0.7, 3: 0.9}[signals]

        return {
            "species": species,
            "stage": stage,
            "feeds": feeds,
            "lang": lang,
            "confidence": confidence,
        }