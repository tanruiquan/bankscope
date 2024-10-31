import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pdfplumber
from dateutil.parser import parse as date_parse

from ._version import __version__
from .constants import categories


@dataclass
class Transaction:
    date: date
    description: str
    amount: float


@dataclass
class Statement:
    transactions: list[Transaction]

    def add_transaction(self, transaction: Transaction):
        self.transactions.append(transaction)


def get_statement_paths(target: Iterable[Path]) -> set[Path]:
    """
    Recursively collects paths to PDF files from a given collection of paths.
    """
    matched_files = set()
    for path in target:
        if path.is_file() and str(path).endswith(".pdf"):
            matched_files.add(path)

        if path.is_dir():
            matched_files |= get_statement_paths(path.iterdir())

    return matched_files


def process_transaction(line: str) -> Transaction:
    parts = line.split()
    date_str = parts[0]
    date = date_parse(date_str, dayfirst=True)
    amount_str = parts[-1]
    if amount_str.startswith("(") and amount_str.endswith(")"):
        amount = -float(amount_str[1:-1])
    else:
        amount = float(amount_str)
    description = " ".join(parts[1:-1])
    return Transaction(date=date, description=description, amount=amount)


def process_statement(file: Path) -> Statement:
    date_pattern = re.compile(r"^\d{2}[A-Z]{3}")

    transactions = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            for line in text.split("\n"):
                if date_pattern.match(line):
                    transactions.append(process_transaction(line))
    return Statement(transactions)


def generate_report(statements: list[Statement]) -> tuple[dict, list[Transaction]]:
    report = {category: 0 for category in categories.keys()}
    others = []
    has_category = False
    for statement in statements:
        for transaction in statement.transactions:
            for category, keywords in categories.items():
                if any(keyword in transaction.description for keyword in keywords):
                    transaction.category = category
                    report[category] += transaction.amount
                    has_category = True
                    break
            if not has_category:
                others.append(transaction)
            has_category = False
    return report, others


def show_report(report: dict, others: list[Transaction]):
    for category, amount in report.items():
        print(f"{category}: {amount:.2f}")
    for transaction in others:
        print(
            f"{transaction.date}: {transaction.description} - {transaction.amount:.2f}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="SG Bank Statement Processor CLI - Generate reports from SG bank statements."
    )
    parser.add_argument("-V", "--version", action="version", version=f"{__version__}")
    parser.add_argument(
        "target",
        nargs="+",
        type=Path,
        help="Path to the directory or file of the bank statement",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to save the generated report as a CSV",
        default="report.csv",
    )

    args = parser.parse_args()

    statement_paths = get_statement_paths(args.target)
    if not statement_paths:
        sys.exit("No PDF files found in the target path.")

    processed_statements = [
        process_statement(statement) for statement in statement_paths
    ]
    report, others = generate_report(processed_statements)
    show_report(report, others)

    # # Output the report
    # report.to_csv(args.output, index=True)
    # print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
