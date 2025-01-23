# Necessary Because otherwise you get problems with permissions and these commands are annoying to type

sudo -E env PATH=$PATH mn --clean > /dev/null 2> /dev/null
sudo -E env PATH=$PATH python $1 "${@:2}"