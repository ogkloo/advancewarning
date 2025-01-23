from sys import argv

import av

def extract_compressed_frames(input_file):
    container = av.open(input_file)
    for packet in container.demux(video=0):  # Focus on video stream
        if packet.stream.type == "video":
            yield bytes(packet)

# Example usage
for i, frame_bytes in enumerate(extract_compressed_frames(argv[1])):
    print(f"Frame {i}: {len(frame_bytes)} bytes")
