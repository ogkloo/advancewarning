# Clean out running instances of similar stuff
sudo killall quictun-server 2> /dev/null
sudo killall quictun-client 2> /dev/null
sudo killall http-server 2> /dev/null
sudo killall iplay

# Build istream player
./istream-player/build.sh 1> /dev/null

# It should clean up after itself anyway but this is worth the 5 seconds it takes
sudo -E env PATH=$PATH mn --clean > /dev/null 2> /dev/null
sudo -E env PATH=$PATH python netemtests.py --video videos/siyuan/multi_resolution.mpd \
videos/lanqiuchang/multi_resolution.mpd \
--results $1
#videos/academic/multi_resolution.mpd \
#videos/runner/multi_resolution.mpd \

#mn --clean > /dev/null 2> /dev/null
#python3 netemtests.py --video videos/siyuan/multi_resolution.mpd --results results/siyuan
#mn --clean > /dev/null 2> /dev/null
#python3 netemtests.py --video videos/runner/multi_resolution.mpd --results results/runner
#mn --clean > /dev/null 2> /dev/null
#python3 netemtests.py --video videos/lanqiuchang/multi_resolution.mpd --results results/lanqiuchang

sudo killall quictun-server 2> /dev/null
sudo killall quictun-client 2> /dev/null
sudo killall http-server 2> /dev/null
sudo killall iplay