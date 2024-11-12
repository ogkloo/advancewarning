import os
import csv
import re
import sys

def collect_file_sizes_by_quality(video_dir):
    """Collects file sizes for each quality-level directory under video_dir, ordered by segment number."""
    quality_file_sizes = []
    
    # Regex to extract segment number from filenames like segment_N.m4s
    segment_regex = re.compile(r"segment_(\d+)\.m4s")

    for root, dirs, files in os.walk(video_dir):
        if files:
            # Filter and sort files based on segment number
            segments = sorted(
                (file for file in files if segment_regex.match(file)),
                key=lambda f: int(segment_regex.match(f).group(1))
            )
            file_sizes = [os.path.getsize(os.path.join(root, segment)) for segment in segments]
            quality_file_sizes.append(file_sizes)
    
    return quality_file_sizes

def write_to_csv(quality_file_sizes, output_csv):
    """Writes the file sizes for each quality level to separate rows in a CSV file."""
    with open(output_csv, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(quality_file_sizes)

if __name__ == "__main__":
    _, video_name = os.path.split(sys.argv[1])
    video_dir = sys.argv[1]  # Set your video directory here
    print(video_name)
    output_csv = f"file_sizes-{video_name}.csv"  # Output CSV file

    quality_file_sizes = collect_file_sizes_by_quality(video_dir)
    write_to_csv(quality_file_sizes, output_csv)
