# Necessary Because otherwise you get problems with permissions and these commands are annoying to type

sudo -E env PATH=$PATH python $1 "${@:2}"