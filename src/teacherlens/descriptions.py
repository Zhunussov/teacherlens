"""Small, explicit crosswalk to public descriptions; never inferred from held-out responses.

Paraphrases of Table 1 in Rittle-Johnson et al. (2025), pp. 22-23:
https://aclanthology.org/2025.aimecon-wip.3/
Only six unambiguous code mappings are used. This is not a complete scoring rubric.
"""

SOURCE = "https://aclanthology.org/2025.aimecon-wip.3/"
DESCRIPTIONS = {
    "WNB": "Fraction numerator and denominator treated as independent whole numbers.",
    "Incomplete": "Solution stops before required fraction simplification or target calculation.",
    "Irrelevant": "Reasoning uses irrelevant features of the mathematical problem.",
    "Additive": "Equivalent fractions compared by differences rather than multiplicative scaling.",
    "Adding_across": "Fraction addition sums numerators and denominators separately.",
    "Duplication": "Fraction multiplication scales both numerator and denominator by the whole number.",
}
