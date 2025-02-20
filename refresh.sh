# Clean out running instances of similar stuff
sudo killall quictun-server 2> /dev/null
sudo killall quictun-client 2> /dev/null
sudo killall http-server 2> /dev/null
sudo killall iplay

# Build istream player
nix-shell --run './istream-player/build.sh 1> /dev/null'

sudo -E env PATH=$PATH mn --clean > /dev/null 2> /dev/null