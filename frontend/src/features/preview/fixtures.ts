/** Development-only figures. Not a statement, not a bank, and not for the production build. */

export const FIXTURE_LABEL =
  "Development-only fixture. Not imported from a statement. No bank is named.";

export type Category =
  | "Groceries"
  | "Dining"
  | "Transport"
  | "Shopping"
  | "Fees and interest"
  | "Other"
  | "Transfers";

export type TxType = "Purchase" | "Refund" | "Fee" | "Payment";

export type FixtureTransaction = {
  id: string;
  date: string;
  description: string;
  arabic?: boolean;
  category: Category;
  card: string;
  type: TxType;
  amount: number;
  statement: string;
  sourcePage: number;
  countsInSpending: boolean;
  note: string;
};

export const cards = {
  everyday: "Everyday card ··4412",
  travel: "Travel card ··9021",
} as const;

export const transactions: FixtureTransaction[] = [
  {
    id: "tx-01",
    date: "2026-09-02",
    description: "Carrefour",
    category: "Groceries",
    card: cards.everyday,
    type: "Purchase",
    amount: 312.4,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 2,
    countsInSpending: true,
    note: "Posted purchase. Counted in September net spending.",
  },
  {
    id: "tx-02",
    date: "2026-09-04",
    description: "لولو هايبرماركت",
    arabic: true,
    category: "Groceries",
    card: cards.everyday,
    type: "Purchase",
    amount: 530.1,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 2,
    countsInSpending: true,
    note: "Arabic description kept as printed. The interface stays English.",
  },
  {
    id: "tx-03",
    date: "2026-09-06",
    description: "Cafe Bateel",
    category: "Dining",
    card: cards.everyday,
    type: "Purchase",
    amount: 86,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 3,
    countsInSpending: true,
    note: "Posted purchase.",
  },
  {
    id: "tx-04",
    date: "2026-09-08",
    description: "Careem",
    category: "Transport",
    card: cards.everyday,
    type: "Purchase",
    amount: 64.25,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 3,
    countsInSpending: true,
    note: "Posted purchase.",
  },
  {
    id: "tx-05",
    date: "2026-09-09",
    description: "Noon",
    category: "Shopping",
    card: cards.travel,
    type: "Purchase",
    amount: 2104.3,
    statement: "Travel card statement, 27 Sep 2026",
    sourcePage: 4,
    countsInSpending: true,
    note: "Largest September purchase. Not a card payment.",
  },
  {
    id: "tx-06",
    date: "2026-09-11",
    description: "The Cheesecake Factory",
    category: "Dining",
    card: cards.travel,
    type: "Purchase",
    amount: 674,
    statement: "Travel card statement, 27 Sep 2026",
    sourcePage: 4,
    countsInSpending: true,
    note: "Posted purchase.",
  },
  {
    id: "tx-07",
    date: "2026-09-12",
    description: "Noon",
    category: "Shopping",
    card: cards.travel,
    type: "Refund",
    amount: -120,
    statement: "Travel card statement, 27 Sep 2026",
    sourcePage: 5,
    countsInSpending: true,
    note: "Refund reduces shopping and net spending. It is not income.",
  },
  {
    id: "tx-08",
    date: "2026-09-15",
    description: "RTA tolls",
    category: "Transport",
    card: cards.everyday,
    type: "Purchase",
    amount: 354.5,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 5,
    countsInSpending: true,
    note: "Posted purchase.",
  },
  {
    id: "tx-09",
    date: "2026-09-18",
    description: "Arabica",
    category: "Dining",
    card: cards.everyday,
    type: "Purchase",
    amount: 500,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 6,
    countsInSpending: true,
    note: "Posted purchase.",
  },
  {
    id: "tx-10",
    date: "2026-09-19",
    description: "Payment received",
    category: "Transfers",
    card: cards.everyday,
    type: "Payment",
    amount: -3100,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 1,
    countsInSpending: false,
    note: "Payment toward the card. Excluded from net spending.",
  },
  {
    id: "tx-11",
    date: "2026-09-21",
    description: "Card fee",
    category: "Fees and interest",
    card: cards.everyday,
    type: "Fee",
    amount: 75,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 7,
    countsInSpending: true,
    note: "Fee included in net spending. August fee in this preview was AED 40.00.",
  },
  {
    id: "tx-12",
    date: "2026-09-25",
    description: "Life Pharmacy",
    category: "Other",
    card: cards.everyday,
    type: "Purchase",
    amount: 190,
    statement: "Everyday card statement, 28 Sep 2026",
    sourcePage: 7,
    countsInSpending: true,
    note: "Posted purchase.",
  },
];

export const netSpending = round2(
  transactions.filter((row) => row.countsInSpending).reduce((sum, row) => sum + row.amount, 0),
);

export const priorNetSpending = 5120.4;
export const fees = 75;
export const priorFees = 40;
export const instalmentRepayment = 500;
export const instalmentPurchase = 6000;
export const shoppingShare = round2(
  (categoryTotal("Shopping") / netSpending) * 100,
);

export const trend = [
  { month: "Apr", net: 3900 },
  { month: "May", net: 4100 },
  { month: "Jun", net: 4550 },
  { month: "Jul", net: 5010 },
  { month: "Aug", net: 5120.4 },
  { month: "Sep", net: netSpending },
];

export const spendingCategories = [
  "Groceries",
  "Dining",
  "Transport",
  "Shopping",
  "Fees and interest",
  "Other",
] as const;

export type SpendingCategory = (typeof spendingCategories)[number];

export function categoryTotal(category: Category) {
  return round2(
    transactions
      .filter((row) => row.countsInSpending && row.category === category)
      .reduce((sum, row) => sum + row.amount, 0),
  );
}

export function rowsFor(category?: string) {
  return transactions.filter((row) => !category || row.category === category);
}

function round2(value: number) {
  return Math.round(value * 100) / 100;
}

const expected = 4770.55;
if (netSpending !== expected) {
  throw new Error(`Development fixture net spending is ${netSpending}, expected ${expected}.`);
}
if (categoryTotal("Groceries") !== 842.5) throw new Error("Grocery fixture drifted.");
if (categoryTotal("Dining") !== 1260) throw new Error("Dining fixture drifted.");
if (categoryTotal("Transport") !== 418.75) throw new Error("Transport fixture drifted.");
if (categoryTotal("Shopping") !== 1984.3) throw new Error("Shopping fixture drifted.");
