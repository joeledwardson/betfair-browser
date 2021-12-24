echo "****************** exporting from poetry to requirements.txt"
echo "installing poetry..."
curl -sSL https://install.python-poetry.org | python3 -
#curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
printf "finished poetry installation..."

printf "\nadding poetry to path"
export PATH="/$HOME/.local/bin:$PATH"

echo "poetry version:"
poetry --version

printf "\nexporting..."
poetry export -f requirements.txt -o requirements.txt --without-hashes

printf "\n****************** done!"