export type ContractSpecification = {
  contract_size_grams: number;
  quote_grams: number;
  purity_fineness: number;
  expiry_rule: string;
};

// Reference specifications are currently documented in Stage 3; no API route exposes them.
export const CONTRACT_SPECS: Record<string, ContractSpecification> = {
  GOLDM: { contract_size_grams: 100, quote_grams: 10, purity_fineness: 995, expiry_rule: '3rd–5th day of expiry month' },
  GOLDTEN: { contract_size_grams: 10, quote_grams: 10, purity_fineness: 999, expiry_rule: '27th–31st day of expiry month' },
  GOLDGUINEA: { contract_size_grams: 8, quote_grams: 8, purity_fineness: 999, expiry_rule: '27th–31st day of expiry month' },
  GOLDPETAL: { contract_size_grams: 1, quote_grams: 1, purity_fineness: 999, expiry_rule: '27th–31st day of expiry month' },
};