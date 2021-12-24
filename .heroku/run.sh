echo "****************** exporting from poetry to requirements.txt"
echo "installing poetry..."
curl -sSL https://install.python-poetry.org | python3 -
#curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
echo "finished poetry instalation..."
echo "poetry version:"
$HOME/.poetry/bin/poetry --version
echo "exporting..."
$HOME/.poetry/bin/poetry export -f requirements.txt -o requirements.txt --without-hashes
echo "****************** done!"