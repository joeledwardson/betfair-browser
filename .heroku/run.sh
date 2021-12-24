echo "******************"
echo "exporting from poetry to requirements.txt"
echo "installing poetry..."
curl -sSL https://install.python-poetry.org | python3 -
#curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
echo "finished poetry installation..."

echo
echo "adding poetry to path"
export PATH="$HOME/.local/bin:$PATH"

echo
echo "poetry version:"
poetry --version

echo
echo "exporting..."
poetry export -f requirements.txt -o requirements.txt --without-hashes

echo
printf "done!"
echo "******************"