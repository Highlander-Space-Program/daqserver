import math

from server.streaming.sensors import DataType


EXPECTED_RANGES = {
    DataType.PT: (-100.0, 2000.0),
    DataType.TC: (-100.0, 1500.0),
    DataType.LC: (-1000.0, 2000.0),
}


class ValidationReport:
    def __init__(self):
        self.total = 0
        self.valid = 0
        self.invalid = 0
        self.non_finite = 0
        self.out_of_range = 0
        self.by_type = {}

    def add(self, output):
        data_type = output.data_type

        if data_type not in self.by_type:
            self.by_type[data_type] = {
                "total": 0,
                "valid": 0,
                "invalid": 0,
            }

        for sample in output.data:
            self.total += 1
            self.by_type[data_type]["total"] += 1

            value = float(sample.value)

            if not math.isfinite(value):
                self.invalid += 1
                self.non_finite += 1
                self.by_type[data_type]["invalid"] += 1
                continue

            low, high = EXPECTED_RANGES.get(
                data_type,
                (-float("inf"), float("inf")),
            )

            if not low <= value <= high:
                self.invalid += 1
                self.out_of_range += 1
                self.by_type[data_type]["invalid"] += 1
                continue

            self.valid += 1
            self.by_type[data_type]["valid"] += 1

    def print_report(self):
        print("\n========== DAQ VALIDATION ==========")
        print(f"Total samples:   {self.total}")
        print(f"Valid samples:   {self.valid}")
        print(f"Invalid samples: {self.invalid}")
        print(f"Non-finite:      {self.non_finite}")
        print(f"Out of range:    {self.out_of_range}")

        print("\nBy sensor type:")

        for data_type, stats in self.by_type.items():
            print(
                f"  {data_type.value}: "
                f"{stats['valid']}/{stats['total']} valid"
            )

        print("====================================\n")


