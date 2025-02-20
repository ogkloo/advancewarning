#! /usr/bin/env bash

# Rebuild istream
#./istream-player/build.sh 1> /dev/null
./refresh.sh 1> /dev/null

# Run test
http-server -p 8080 ./videos/runner 2> /dev/null &
server_pid=$!

nix-shell --run './istream-player/istream \
    --mod_downloader tcp \
    --mod_abr bandwidth \
    --max_buffer 3 \
    --search_method explicit \
    -i http://127.0.0.1:8080/multi_resolution.mpd \
    1> tmp/tests/stdout.txt \
    2> tmp/tests/stderr.txt'

# Cleanup
kill $server_pid &> /dev/null