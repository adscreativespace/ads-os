"""
ADS OS Desktop -- Shared constants
"""

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi (NCT)", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
]

# Unified country list: selecting one sets both the Country Name and the
# Mobile Country Code together (Decision 033's "Country is a parent field").
# Not exhaustive -- covers countries ADS is realistically likely to deal with;
# expand as real foreign clients come in rather than importing all ~195 upfront.
COUNTRIES = [
    ("United States", "+1"), ("Canada", "+1"), ("United Kingdom", "+44"),
    ("Australia", "+61"), ("United Arab Emirates", "+971"), ("Saudi Arabia", "+966"),
    ("Singapore", "+65"), ("Malaysia", "+60"), ("Qatar", "+974"), ("Oman", "+968"),
    ("Bahrain", "+973"), ("Kuwait", "+965"), ("New Zealand", "+64"), ("Germany", "+49"),
    ("France", "+33"), ("Italy", "+39"), ("Spain", "+34"), ("Netherlands", "+31"),
    ("Switzerland", "+41"), ("Sweden", "+46"), ("Norway", "+47"), ("Japan", "+81"),
    ("South Korea", "+82"), ("China", "+86"), ("Hong Kong", "+852"), ("Thailand", "+66"),
    ("Philippines", "+63"), ("South Africa", "+27"), ("Kenya", "+254"),
    ("Bangladesh", "+880"), ("Pakistan", "+92"), ("Sri Lanka", "+94"), ("Nepal", "+977"),
    ("Other", ""),
]

INDIA_COUNTRY_CODE = "+91"


def country_label(name, code):
    return f"{name} ({code})" if code else name


def country_from_label(label, countries=COUNTRIES):
    for name, code in countries:
        if country_label(name, code) == label:
            return name, code
    return countries[-1]  # "Other"


def apply_numeric_only(root, ctk_entry, max_length=None):
    """
    Restricts a CTkEntry to digit-only input as the user types.
    `root` must be the Tk/CTk/CTkToplevel window the entry lives in (needed
    for .register()). CTkEntry doesn't expose `validate`/`validatecommand`
    directly, so this reaches into its internal tkinter Entry widget.
    """
    def _validate(proposed):
        if proposed == "":
            return True
        if not proposed.isdigit():
            return False
        if max_length and len(proposed) > max_length:
            return False
        return True

    vcmd = (root.register(_validate), "%P")
    ctk_entry._entry.configure(validate="key", validatecommand=vcmd)


def apply_decimal_only(root, ctk_entry, max_length=None):
    """
    Like apply_numeric_only, but allows a single decimal point (for areas,
    currency amounts, distances -- values that are legitimately fractional).
    """
    def _validate(proposed):
        if proposed == "":
            return True
        if proposed.count(".") > 1:
            return False
        if not proposed.replace(".", "", 1).isdigit():
            return False
        if max_length and len(proposed) > max_length:
            return False
        return True

    vcmd = (root.register(_validate), "%P")
    ctk_entry._entry.configure(validate="key", validatecommand=vcmd)


import re

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Zz][A-Z\d]$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

COMMON_DOMAIN_TYPOS = {
    "gmial.com": "gmail.com", "gmil.com": "gmail.com", "gmai.com": "gmail.com",
    "gmal.com": "gmail.com", "hotnail.com": "hotmail.com", "hotmial.com": "hotmail.com",
    "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
}


def is_valid_email(value):
    value = value.strip()
    if ".." in value:
        return False
    return bool(EMAIL_PATTERN.match(value))


def email_typo_suggestion(value):
    """Returns a suggested correction if the domain matches a known typo, else None."""
    value = value.strip()
    if "@" not in value:
        return None
    local, _, domain = value.partition("@")
    corrected = COMMON_DOMAIN_TYPOS.get(domain.lower())
    return f"{local}@{corrected}" if corrected else None


def is_valid_gstin(value):
    return bool(GSTIN_PATTERN.match(value.strip().upper()))


def is_valid_pan(value):
    return bool(PAN_PATTERN.match(value.strip().upper()))


def format_mobile_display(number):
    """'7003196240' -> '70031 96240' for readability. Storage stays unformatted."""
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if len(digits) <= 5:
        return digits
    return f"{digits[:5]} {digits[5:]}"


def to_title_case(text):
    return text.strip().title() if text else text
