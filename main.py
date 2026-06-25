from typing import Literal, get_args, cast, Final
import pdfplumber

Month = Literal["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Nov", "Dec"]
Day = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

TEST_ADDRESS: Final[str] = "PLEASE SET ME TO THE ADDRESS OF THE PDF FILE"

assert TEST_ADDRESS != "PLEASE SET ME TO THE ADDRESS OF THE PDF FILE", "Please set the TEST_ADDRESS variable to the address of the PDF file."


class DataDay:
    def __init__(self, date: int, day: Day, data_mb: float | int) -> None:
        self.date: Final[int] = date
        self.day: Final[Day] = day
        self.total_data_mb: float = data_mb


class DataMonth:
    def __init__(self, month: Month) -> None:
        self.month: Final[Month] = month
        self.total_data_mb: float = 0.0
        self.data_days: dict[int, DataDay] = {}

    def add(self, day: Day, date: int, data_mb: float | int):
        if not (self.data_days.get(date) is None):
            if self.data_days[date].total_data_mb != 0.0:
                return
        self.data_days[date] = DataDay(date, day, data_mb)


class DataYear:
    def __init__(self, year: str) -> None:
        self.year: Final[str] = year
        self.total_data_mb: float = 0.0
        self.data_months: dict[Month, DataMonth] = {}

    def add_if_absent(self, month: Month, data_mb: float | int = 0.0):
        if self.data_months.get(month) is None:
            self.data_months[month] = DataMonth(month)
        self.data_months[month].total_data_mb += data_mb


class PhoneNumber:
    def __init__(self, number: str) -> None:
        self.number: Final[str] = number
        self.total_data_mb: float | int = 0.0
        self.data_years: dict[str, DataYear] = {}

    def add_if_absent(self, year: str):
        if self.data_years.get(year) is None:
            self.data_years[year] = DataYear(year)

    def add_entry(self, year: str, month: Month, date: int, day: Day, data_mb: float | int):
        self.total_data_mb += data_mb
        self.data_years[year].total_data_mb += data_mb
        self.data_years[year].add_if_absent(month, data_mb)
        self.data_years[year].data_months[month].add(day, date, data_mb)


def get_year_month(first_page: list[str]) -> tuple[str, Month]:
    parsed_line: list[str] = first_page[1].split()
    month = parsed_line[1][0:3]
    year = parsed_line[2]
    assert month in get_args(Month)
    return year, cast(Month, month)


def get_numbers(first_page: list[str]) -> set[str]:
    numbers: Final[set[str]] = set()
    for line in first_page:
        if line.startswith("Mobile ("):
            numbers.add(line[8:-1])
    return numbers


def get_document(address: str) -> list[list[str]]:
    with pdfplumber.open(address) as pdf:
        raw_doc = [p.extract_text() or "" for p in pdf.pages]
    return [line.split("\n") for line in raw_doc]


def get_year(document_year: str, document_month: Month, page_month: Month) -> str:
    """
    Returns the previous year if the page month is Dec and the document month is Jan or Feb.
    """
    if page_month == 'Dec' and (document_month == 'Jan' or document_month == 'Feb'):
        return str(int(document_year) - 1)
    return document_year


def get_data(document: list[list[str]], numbers: set[str]) -> dict[str, PhoneNumber]:
    phone_numbers: dict[str, PhoneNumber] = {number: PhoneNumber(number) for number in numbers}
    year, document_month = get_year_month(document[0])
    is_data = False
    for page in document:
        number: str = page[3][8:-1]
        for line in page:
            if line == "Date Volume (MB) Included? VAT Ex. VAT rate VAT Inc.":
                is_data = True
                continue
            if is_data:
                line: list[str] = line.split()
                if not (line[0] in get_args(Day)):
                    is_data = False
                    continue
                if line[0] in get_args(Day) and line[2] in get_args(Month):
                    if phone_numbers[number].data_years.get(year) is None:
                        phone_numbers[number].data_years[year] = DataYear(year)
                    # Parse values
                    day: Day = cast(Day, line[0])
                    date: int = int(line[1])
                    line_month: Month = cast(Month, line[2])
                    data_mb = float(line[3])
                    # Parse end
                    year: str = get_year(year, document_month, line_month)
                    phone_numbers[number].add_if_absent(year)
                    phone_numbers[number].add_entry(year, line_month, date, day, data_mb)
    return phone_numbers


def main():
    document: list[list[str]] = get_document(TEST_ADDRESS)
    numbers: set[str] = get_numbers(document[0])
    data: dict[str, PhoneNumber] = get_data(document, numbers)
    for number in numbers:
        number_data = data[number]
        print(f"{number}:")
        print(f"\tTotal data usage: {number_data.total_data_mb} MB")
        for year, data_year in number_data.data_years.items():
            print(f"\t{year}:")
            print(f"\t\tTotal data usage: {data_year.total_data_mb} MB")
            for month, data_month in data_year.data_months.items():
                print(f"\t\t{month}:")
                print(f"\t\t\tTotal data usage: {data_month.total_data_mb} MB")
                for date, data_day in data_month.data_days.items():
                    print(f"\t\t\t\t{date}: {data_day.total_data_mb} MB")
        print("-------------------------------------------------------------------------------------------")


if __name__ == "__main__":
    main()
