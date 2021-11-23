curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
$HOME/.poetry/bin/poetry export -f requirements.txt -o requirements.txt --without-hashes