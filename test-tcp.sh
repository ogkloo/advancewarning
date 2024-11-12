sudo killall quictun-server
sudo killall quictun-client
sudo killall http-server

# It should clean up after itself anyway but this is worth the 5 seconds it takes
sudo -E env PATH=$PATH mn --clean > /dev/null 2> /dev/null
sudo -E env PATH=$PATH python3 netemtests.py -c --tcp
sudo -E env PATH=$PATH mn --clean > /dev/null 2> /dev/null

sudo killall quictun-server
sudo killall quictun-client
sudo killall http-server