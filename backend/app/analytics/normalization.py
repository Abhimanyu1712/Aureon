from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext


@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    contract_size_grams: Decimal
    quote_grams: Decimal
    purity_fineness: int
    expiry_rule: str


@dataclass(frozen=True)
class NormalizedPrice:
    normalized_price_per_gram: Decimal
    purity_adjusted_price_per_gram: Decimal


CONTRACT_SPECS: dict[str, ContractSpec] = {
    "GOLDM": ContractSpec(
        symbol="GOLDM",
        contract_size_grams=Decimal("100"),
        quote_grams=Decimal("10"),
        purity_fineness=995,
        expiry_rule="3rd-5th day of the expiry month",
    ),
    "GOLDTEN": ContractSpec(
        symbol="GOLDTEN",
        contract_size_grams=Decimal("10"),
        quote_grams=Decimal("10"),
        purity_fineness=999,
        expiry_rule="27th-31st day of the expiry month",
    ),
    "GOLDGUINEA": ContractSpec(
        symbol="GOLDGUINEA",
        contract_size_grams=Decimal("8"),
        quote_grams=Decimal("8"),
        purity_fineness=999,
        expiry_rule="27th-31st day of the expiry month",
    ),
    "GOLDPETAL": ContractSpec(
        symbol="GOLDPETAL",
        contract_size_grams=Decimal("1"),
        quote_grams=Decimal("1"),
        purity_fineness=999,
        expiry_rule="27th-31st day of the expiry month",
    ),
}

REFERENCE_FINENESS = Decimal("999")


def get_contract_spec(symbol: str) -> ContractSpec:
    normalized_symbol = symbol.strip().upper()
    try:
        return CONTRACT_SPECS[normalized_symbol]
    except KeyError as exc:
        raise ValueError(f"Unsupported gold contract symbol: {symbol!r}") from exc


def normalize_price_to_purity_adjusted_rupees_per_gram(
    symbol: str,
    quoted_price: Decimal | int | float | str | None,
) -> NormalizedPrice:
    if quoted_price is None or isinstance(quoted_price, bool):
        raise ValueError("Quoted price must be a finite positive number.")
    try:
        price = Decimal(str(quoted_price))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Quoted price must be a finite positive number.") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("Quoted price must be a finite positive number.")

    spec = get_contract_spec(symbol)
    with localcontext() as context:
        context.prec = 28
        # First recover the whole-contract value from its quoted gram basis,
        # then divide by contract size to get observed rupees per gram.
        contract_value = price * spec.contract_size_grams / spec.quote_grams
        normalized_per_gram = contract_value / spec.contract_size_grams
        # Convert to the common 999-fineness basis: a 995 quote is scaled by
        # 999/995 because a 999-fineness gram contains more fine gold.
        purity_adjusted_per_gram = (
            normalized_per_gram
            * REFERENCE_FINENESS
            / Decimal(spec.purity_fineness)
        )
    return NormalizedPrice(
        normalized_price_per_gram=normalized_per_gram,
        purity_adjusted_price_per_gram=purity_adjusted_per_gram,
    )