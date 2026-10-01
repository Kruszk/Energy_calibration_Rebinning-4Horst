#!/usr/bin/env python3
import argparse
import math
import os
import sys

# Calibration Parameters: E(ch) = Intercept + Gradient * ch
INTERCEPT = 7.364777
INTERCEPT_ERR = 0.007649
GRADIENT = 0.725058
GRADIENT_ERR = 0.000003

# Target Rebinning Specifications
TARGET_BINS = 12000
BIN_WIDTH = 1.0  # 1 keV per bin


def read_tka(path):
    """Reads ASCII TKA spectrum file containing channel counts and metadata."""
    counts = []
    real_time = 0.0
    live_time = 0.0

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                counts.append(float(line_str))
            except ValueError:
                low = line_str.lower()
                if "real" in low:
                    try:
                        real_time = float(line_str.split()[-1])
                    except Exception:
                        pass
                elif "live" in low:
                    try:
                        live_time = float(line_str.split()[-1])
                    except Exception:
                        pass

    return {
        "counts": counts,
        "n_channels": len(counts),
        "real_time": real_time,
        "live_time": live_time,
    }


def rebin_to_1kev(raw_counts, n_bins=TARGET_BINS, bin_w=BIN_WIDTH):
    """Performs area-preserving fractional rebinning into 1 keV energy bins."""
    rebinned = [0.0] * n_bins

    for ch, count in enumerate(raw_counts):
        if count <= 0:
            continue

        # Energy boundary of channel ch [ch - 0.5, ch + 0.5]
        e_low = INTERCEPT + GRADIENT * (ch - 0.5)
        e_high = INTERCEPT + GRADIENT * (ch + 0.5)

        if e_high <= 0 or e_low >= (n_bins * bin_w):
            continue

        e_start = max(0.0, e_low)
        e_end = min(float(n_bins * bin_w), e_high)

        if e_end <= e_start:
            continue

        count_density = count / (e_high - e_low)

        first_bin = max(0, int(math.floor(e_start / bin_w)))
        last_bin = min(n_bins - 1, int(math.floor(e_end / bin_w)))

        for b in range(first_bin, last_bin + 1):
            bin_low = b * bin_w
            bin_high = (b + 1) * bin_w
            overlap = max(0.0, min(e_end, bin_high) - max(e_start, bin_low))
            rebinned[b] += count_density * overlap

    return rebinned


def write_horst(data, rebinned_counts, output_path):
    """Writes 1 keV rebinned spectrum to horst format."""
    with open(output_path, "w", encoding="utf-8") as f:
        if data["real_time"] > 0 or data["live_time"] > 0:
            f.write(
                f"# Real_Time: {data['real_time']:.2f} s | Live_Time:"
                f" {data['live_time']:.2f} s\n"
            )
        f.write("# Bin\tEnergy_keV\tEnergy_Err\tCounts\tCounts_Err\n")

        for b, count in enumerate(rebinned_counts):
            energy_center = (b + 0.5) * BIN_WIDTH

            # Calibration uncertainty at energy center
            ch_equiv = (energy_center - INTERCEPT) / GRADIENT
            energy_err = math.sqrt(
                (INTERCEPT_ERR**2) + ((ch_equiv * GRADIENT_ERR) ** 2)
            )
            count_err = math.sqrt(count) if count >= 0 else 0.0

            f.write(
                f"{b:5d}\t{energy_center:12.6f}\t{energy_err:10.6f}\t{count:10.2f}\t{count_err:10.2f}\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Convert and rebin .TKA files to 1 keV/bin (12000 bins)."
    )
    parser.add_argument("input", help="Path to input .TKA file")
    parser.add_argument(
        "-o", "--output", help="Path to output file", default=None
    )

    args = parser.parse_args()

    out_path = (
        args.output
        if args.output
        else os.path.splitext(args.input)[0] + "_horst.txt"
    )

    spectrum_data = read_tka(args.input)
    rebinned = rebin_to_1kev(spectrum_data["counts"])
    write_horst(spectrum_data, rebinned, out_path)

    print(
        f"Successfully rebinned '{args.input}' -> 12000 bins (1 keV/bin) saved"
        f" to '{out_path}'"
    )


if __name__ == "__main__":
    main()#!/usr/bin/env python3
import argparse
import math
import os
import sys

# Calibration Parameters: E(ch) = Intercept + Gradient * ch
INTERCEPT = 7.364777
INTERCEPT_ERR = 0.007649
GRADIENT = 0.725058
GRADIENT_ERR = 0.000003


def read_tka(path):
    """Reads ASCII TKA spectrum file containing channel counts and metadata."""
    counts = []
    real_time = 0.0
    live_time = 0.0

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                counts.append(float(line_str))
            except ValueError:
                low = line_str.lower()
                if "real" in low:
                    try:
                        real_time = float(line_str.split()[-1])
                    except Exception:
                        pass
                elif "live" in low:
                    try:
                        live_time = float(line_str.split()[-1])
                    except Exception:
                        pass

    return {
        "counts": counts,
        "n_channels": len(counts),
        "real_time": real_time,
        "live_time": live_time,
        "cal": [INTERCEPT, GRADIENT, 0.0, 0.0],
        "cal_err": [INTERCEPT_ERR, GRADIENT_ERR, 0.0, 0.0],
    }


def write_horst(data, output_path):
    """Writes calibrated energy, propagated uncertainties, and counts."""
    c0, c1 = data["cal"][0], data["cal"][1]
    c0_err, c1_err = data["cal_err"][0], data["cal_err"][1]

    with open(output_path, "w", encoding="utf-8") as f:
        if data["real_time"] > 0 or data["live_time"] > 0:
            f.write(
                f"# Real_Time: {data['real_time']:.2f} s | Live_Time:"
                f" {data['live_time']:.2f} s\n"
            )
        f.write("# Channel\tEnergy_keV\tEnergy_Err\tCounts\tCounts_Err\n")

        for ch, count in enumerate(data["counts"]):
            energy = c0 + (c1 * ch)
            energy_err = math.sqrt((c0_err**2) + ((ch * c1_err) ** 2))
            count_err = math.sqrt(count) if count >= 0 else 0.0

            f.write(
                f"{ch:5d}\t{energy:12.6f}\t{energy_err:10.6f}\t{count:10.0f}\t{count_err:10.2f}\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert .tka ASCII files using specific linear calibration"
            " parameters."
        )
    )
    parser.add_argument("input", help="Path to input .tka spectrum file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output file (default: <input>_horst.txt)",
        default=None,
    )

    args = parser.parse_args()

    # Automatically defaults output format to <filename>_horst.txt
    if args.output:
        out_path = args.output
    else:
        out_path = os.path.splitext(args.input)[0] + "_horst.txt"

    spectrum_data = read_tka(args.input)
    write_horst(spectrum_data, out_path)
    print(
        f"Processed {spectrum_data['n_channels']} channels -> Saved to"
        f" '{out_path}'"
    )


if __name__ == "__main__":
    main()#!/usr/bin/env python3
import argparse
import math
import sys

# Calibration Parameters: E(ch) = Intercept + Gradient * ch
INTERCEPT = 7.364777
INTERCEPT_ERR = 0.007649
GRADIENT = 0.725058
GRADIENT_ERR = 0.000003


def read_tka(path):
    """Reads ASCII TKA spectrum file containing channel counts and metadata."""
    counts = []
    real_time = 0.0
    live_time = 0.0

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                counts.append(float(line_str))
            except ValueError:
                # Read metadata comments if present
                low = line_str.lower()
                if "real" in low:
                    try:
                        real_time = float(line_str.split()[-1])
                    except Exception:
                        pass
                elif "live" in low:
                    try:
                        live_time = float(line_str.split()[-1])
                    except Exception:
                        pass

    return {
        "counts": counts,
        "n_channels": len(counts),
        "real_time": real_time,
        "live_time": live_time,
        "cal": [INTERCEPT, GRADIENT, 0.0, 0.0],  # [c0, c1, c2, c3]
        "cal_err": [INTERCEPT_ERR, GRADIENT_ERR, 0.0, 0.0],
    }


def write_horst(data, output_path):
    """Writes calibrated energy, propagated uncertainties, and counts."""
    c0, c1 = data["cal"][0], data["cal"][1]
    c0_err, c1_err = data["cal_err"][0], data["cal_err"][1]

    with open(output_path, "w", encoding="utf-8") as f:
        # Header with metadata
        if data["real_time"] > 0 or data["live_time"] > 0:
            f.write(
                f"# Real_Time: {data['real_time']:.2f} s | Live_Time: {data['live_time']:.2f} s\n"
            )
        f.write("# Channel\tEnergy_keV\tEnergy_Err\tCounts\tCounts_Err\n")

        for ch, count in enumerate(data["counts"]):
            # Energy calculation: E = c0 + c1 * ch
            energy = c0 + (c1 * ch)

            # Error propagation: sigma_E = sqrt(sigma_c0^2 + (ch * sigma_c1)^2)
            energy_err = math.sqrt((c0_err**2) + ((ch * c1_err) ** 2))

            # Poisson count uncertainty: sigma_N = sqrt(N)
            count_err = math.sqrt(count) if count >= 0 else 0.0

            f.write(
                f"{ch:5d}\t{energy:12.6f}\t{energy_err:10.6f}\t{count:10.0f}\t{count_err:10.2f}\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Convert .tka ASCII files using specific linear calibration parameters."
    )
    parser.add_argument("input", help="Path to input .tka spectrum file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output file (default: <input>_calibrated.dat)",
        default=None,
    )

    args = parser.parse_args()

    # Determine default output file name if not provided
    if args.output:
        out_path = args.output
    else:
        out_path = args.input.rsplit(".", 1)[0] + "_calibrated.dat"

    spectrum_data = read_tka(args.input)
    write_horst(spectrum_data, out_path)
    print(
        f"Processed {spectrum_data['n_channels']} channels -> Saved to '{out_path}'"
    )


if __name__ == "__main__":
    main()
